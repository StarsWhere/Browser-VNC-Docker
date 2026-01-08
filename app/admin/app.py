import logging
import os
import subprocess
import sys
import time
from logging.handlers import RotatingFileHandler
from typing import Dict, List

from flask import Flask, jsonify, render_template, request

sys.path.append("/app")
from common import accounts  # noqa: E402

app = Flask(__name__, template_folder="templates", static_folder="static")

START_TIME = time.time()


def _clipboard_env():
    env = os.environ.copy()
    env["DISPLAY"] = accounts.DISPLAY
    return env


def read_clipboard() -> str:
    try:
        result = subprocess.run(
            ["xclip", "-selection", "clipboard", "-o"],
            capture_output=True,
            text=True,
            env=_clipboard_env(),
            timeout=3,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("clipboard read timed out")
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        if "target STRING not available" in stderr:
            return ""
        raise RuntimeError(stderr or "xclip read failed")
    return result.stdout


def write_clipboard(content: str) -> None:
    try:
        result = subprocess.run(
            ["xclip", "-selection", "clipboard", "-i"],
            input=content,
            text=True,
            capture_output=True,
            env=_clipboard_env(),
            timeout=3,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("clipboard write timed out")
    if result.returncode != 0:
        raise RuntimeError((result.stderr or "").strip() or "xclip write failed")


def configure_logging():
    log_dir = accounts.LOG_DIR
    os.makedirs(log_dir, exist_ok=True)
    max_bytes = int(os.environ.get("LOG_MAX_BYTES", "10485760"))
    backup_count = int(os.environ.get("LOG_BACKUP_COUNT", "5"))
    handler = RotatingFileHandler(
        os.path.join(log_dir, "admin-error.log"),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(formatter)
    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)


configure_logging()


def api_response(code: int = 0, message: str = "ok", data=None, http_status: int = 200):
    return jsonify({"code": code, "message": message, "data": data}), http_status


def serialize_account(acc_obj: Dict, with_running: bool = True) -> Dict:
    result = dict(acc_obj)
    if with_running:
        result["running"] = accounts.is_running(acc_obj["profile_dir"])
    return result


def get_accounts() -> List[Dict]:
    return accounts.load_accounts()


@app.errorhandler(accounts.ValidationError)
def handle_validation_error(err: accounts.ValidationError):
    code = err.code
    status = 400 if code == 1001 else 409 if code == 1007 else 500
    return api_response(code=code, message=str(err), data=None, http_status=status)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/health")
def health():
    def proc_alive(pattern: str) -> bool:
        return (
            subprocess.run(
                ["pgrep", "-f", pattern],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode
            == 0
        )

    processes = {
        "xvnc": proc_alive("Xvnc :1"),
        "websockify": proc_alive("websockify .*5901"),
        "gunicorn": proc_alive("gunicorn"),
    }
    status = "healthy" if all(processes.values()) else "degraded"
    return api_response(
        data={
            "status": status,
            "uptime_seconds": int(time.time() - START_TIME),
            "processes": processes,
        }
    )


@app.route("/api/clipboard", methods=["GET"])
def get_clipboard():
    try:
        content = read_clipboard()
    except Exception as exc:
        app.logger.exception("failed to read clipboard")
        return api_response(code=1010, message="failed to read clipboard", data={"reason": str(exc)}, http_status=500)
    return api_response(data={"content": content})


@app.route("/api/clipboard", methods=["POST"])
def set_clipboard():
    payload = request.get_json(silent=True) or {}
    content = payload.get("content", "")
    if not isinstance(content, str):
        return api_response(code=1001, message="content must be string", data=None, http_status=400)
    try:
        write_clipboard(content)
    except Exception as exc:
        app.logger.exception("failed to write clipboard")
        return api_response(code=1011, message="failed to write clipboard", data={"reason": str(exc)}, http_status=500)
    return api_response(data={"content": content})


@app.route("/api/accounts", methods=["GET"])
def list_accounts():
    accs = [serialize_account(item) for item in get_accounts()]
    return api_response(data={"accounts": accs})


@app.route("/api/accounts/<account_id>", methods=["GET"])
def get_account(account_id: str):
    accs = get_accounts()
    target = accounts.find_account(accs, account_id)
    if not target:
        return api_response(code=1002, message="account not found", data=None, http_status=404)
    return api_response(data={"account": serialize_account(target)})


@app.route("/api/accounts", methods=["POST"])
def create_account():
    payload = request.get_json(silent=True) or {}
    cleaned = accounts.validate_account_payload(payload, partial=False)
    new_account = accounts.build_account(cleaned)
    items = get_accounts()
    items.append(new_account)
    accounts.save_accounts(items)
    accounts.ensure_profile(new_account)
    app.logger.info("created account %s", new_account["id"])
    return api_response(data={"account": serialize_account(new_account, with_running=False)})


@app.route("/api/accounts/<account_id>", methods=["PUT"])
def update_account(account_id: str):
    payload = request.get_json(silent=True) or {}
    cleaned = accounts.validate_account_payload(payload, partial=True)
    items = get_accounts()
    target = accounts.find_account(items, account_id)
    if not target:
        return api_response(code=1002, message="account not found", data=None, http_status=404)
    try:
        updated = accounts.update_account_obj(target, cleaned, check_version="version" in cleaned)
    except accounts.ValidationError as e:
        if e.code == 1007:
            return api_response(
                code=1007,
                message="version conflict",
                data={"expected_version": cleaned.get("version"), "actual_version": target.get("version")},
                http_status=409,
            )
        raise
    accounts.save_accounts(items)
    accounts.ensure_profile(updated)
    app.logger.info("updated account %s", account_id)
    return api_response(data={"account": serialize_account(updated)})


@app.route("/api/accounts/<account_id>", methods=["DELETE"])
def delete_account(account_id: str):
    delete_profile = request.args.get("delete_profile", "false").lower() == "true"
    items = get_accounts()
    target = accounts.find_account(items, account_id)
    if target:
        items = [a for a in items if a.get("id") != account_id]
        accounts.save_accounts(items)
        profile_path = target.get("profile_dir")
    else:
        accounts.save_accounts(items)
        profile_path = os.path.join(accounts.PROFILES_DIR, account_id)
    if delete_profile:
        accounts.delete_profile_dir(profile_path)
    result = "deleted" if target else "already_deleted"
    return api_response(data={"result": result, "delete_profile": delete_profile})


@app.route("/api/accounts/<account_id>/start", methods=["POST"])
def start_account(account_id: str):
    items = get_accounts()
    target = accounts.find_account(items, account_id)
    if not target:
        return api_response(code=1002, message="account not found", data=None, http_status=404)
    try:
        _, status = accounts.start_account(target)
    except Exception as exc:  # pragma: no cover
        app.logger.exception("launch failed for %s", account_id)
        return api_response(
            code=1008,
            message="failed to launch browser",
            data={"account_id": account_id, "reason": str(exc)},
            http_status=500,
        )
    return api_response(data={"status": status})


@app.route("/api/accounts/<account_id>/stop", methods=["POST"])
def stop_account(account_id: str):
    items = get_accounts()
    target = accounts.find_account(items, account_id)
    if not target:
        return api_response(code=1002, message="account not found", data=None, http_status=404)
    _, status = accounts.stop_account(target)
    if status == "stop_failed":
        return api_response(code=1008, message="failed to stop browser", data={"account_id": account_id}, http_status=500)
    return api_response(data={"status": status})


@app.route("/api/accounts/start_all_autostart", methods=["POST"])
def start_all_autostart():
    items = get_accounts()
    started = []
    already = []
    for acc in items:
        if not acc.get("autostart"):
            continue
        _, status = accounts.start_account(acc)
        if status == "started":
            started.append(acc["id"])
        else:
            already.append(acc["id"])
    return api_response(data={"started": started, "already_running": already})
