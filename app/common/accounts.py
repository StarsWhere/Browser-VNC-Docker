import fcntl
import json
import logging
import os
import re
import secrets
import shutil
import subprocess
import time
from typing import Dict, List, Optional, Tuple

DATA_DIR = os.environ.get("DATA_DIR", "/data")
PROFILES_DIR = os.path.join(DATA_DIR, "profiles")
LOG_DIR = os.path.join(DATA_DIR, "logs")
ACCOUNTS_FILE = os.path.join(DATA_DIR, "accounts.json")
LAUNCHER_LOG = os.path.join(LOG_DIR, "launcher.log")
DISPLAY = os.environ.get("VNC_DISPLAY", ":1")

log = logging.getLogger(__name__)


class ValidationError(Exception):
    def __init__(self, message: str, code: int = 1001):
        super().__init__(message)
        self.code = code


def ensure_data_dirs() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(PROFILES_DIR, exist_ok=True)
    os.makedirs(LOG_DIR, exist_ok=True)
    if not os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            f.write("[]")


def _with_lock(mode: str):
    f = open(ACCOUNTS_FILE, mode, encoding="utf-8")
    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
    return f


def load_accounts() -> List[Dict]:
    ensure_data_dirs()
    with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            raise ValidationError("accounts.json is not valid JSON", code=1006)
    return data


def save_accounts(accounts: List[Dict]) -> None:
    ensure_data_dirs()
    with _with_lock("w") as f:
        json.dump(accounts, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def generate_account_id() -> str:
    ts = int(time.time() * 1000)
    suffix = secrets.token_hex(3)
    return f"acc-{ts}-{suffix}"


def _validate_proxy_obj(proxy_obj: Dict, prefix: str) -> Dict:
    if not isinstance(proxy_obj, dict):
        raise ValidationError(f"{prefix} must be object")
    host = proxy_obj.get("host")
    port = proxy_obj.get("port")
    if not isinstance(host, str) or not host.strip():
        raise ValidationError(f"{prefix}.host is required")
    if not isinstance(port, int) or not (1 <= port <= 65535):
        raise ValidationError(f"{prefix}.port must be between 1 and 65535")
    username = proxy_obj.get("username")
    password = proxy_obj.get("password")
    if username is not None and not isinstance(username, str):
        raise ValidationError(f"{prefix}.username must be string")
    if password is not None and not isinstance(password, str):
        raise ValidationError(f"{prefix}.password must be string")
    if username is not None and len(username) > 256:
        raise ValidationError(f"{prefix}.username too long")
    if password is not None and len(password) > 256:
        raise ValidationError(f"{prefix}.password too long")
    return {
        "host": host.strip(),
        "port": port,
        "username": username if username is not None else "",
        "password": password if password is not None else "",
    }


def validate_proxy(proxy: Optional[Dict]) -> Dict:
    if proxy is None:
        return {}
    if not isinstance(proxy, dict):
        raise ValidationError("proxy must be object")
    result: Dict[str, Dict] = {}
    for key in ("http", "https", "socks5"):
        if key in proxy and proxy[key] is not None:
            result[key] = _validate_proxy_obj(proxy[key], f"proxy.{key}")
    return result


def validate_account_payload(data: Dict, partial: bool = False) -> Dict:
    if not isinstance(data, dict):
        raise ValidationError("payload must be object")
    cleaned: Dict = {}
    if "name" in data or not partial:
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValidationError("name is required")
        if len(name) > 128:
            raise ValidationError("name too long")
        cleaned["name"] = name.strip()
    if "proxy" in data:
        cleaned["proxy"] = validate_proxy(data.get("proxy"))
    autostart = data.get("autostart")
    if "autostart" in data:
        if not isinstance(autostart, bool):
            raise ValidationError("autostart must be boolean")
        cleaned["autostart"] = autostart
    elif not partial:
        cleaned["autostart"] = False
    if "default_url" in data:
        default_url = data.get("default_url")
        if default_url is not None:
            if not isinstance(default_url, str):
                raise ValidationError("default_url must be string")
            default_url = default_url.strip()
            if default_url and not default_url.lower().startswith(("http://", "https://")):
                raise ValidationError("default_url must start with http or https")
        cleaned["default_url"] = default_url or ""
    elif not partial:
        cleaned["default_url"] = ""
    if "notes" in data:
        notes = data.get("notes")
        if notes is not None and not isinstance(notes, str):
            raise ValidationError("notes must be string")
        if isinstance(notes, str) and len(notes) > 1024:
            raise ValidationError("notes too long")
        cleaned["notes"] = notes or ""
    elif not partial:
        cleaned["notes"] = ""
    if "version" in data:
        version = data.get("version")
        if not isinstance(version, int):
            raise ValidationError("version must be int")
        cleaned["version"] = version
    return cleaned


def build_account(cleaned: Dict) -> Dict:
    account_id = generate_account_id()
    profile_dir = os.path.join(PROFILES_DIR, account_id)
    return {
        "id": account_id,
        "name": cleaned["name"],
        "profile_dir": profile_dir,
        "proxy": cleaned.get("proxy", {}),
        "autostart": cleaned.get("autostart", False),
        "default_url": cleaned.get("default_url", ""),
        "notes": cleaned.get("notes", ""),
        "version": 1,
    }


def update_account_obj(account: Dict, cleaned: Dict, check_version: bool = False) -> Dict:
    if check_version and "version" in cleaned:
        if account.get("version") != cleaned["version"]:
            raise ValidationError("version conflict", code=1007)
    for key in ("name", "proxy", "autostart", "default_url", "notes"):
        if key in cleaned:
            account[key] = cleaned[key]
    account["version"] = account.get("version", 1) + 1
    return account


def find_account(accounts: List[Dict], account_id: str) -> Optional[Dict]:
    for item in accounts:
        if item.get("id") == account_id:
            return item
    return None


def _user_pref(key: str, value) -> str:
    if isinstance(value, bool):
        val = "true" if value else "false"
    elif isinstance(value, int):
        val = str(value)
    else:
        val = json.dumps(value)
    return f'user_pref("{key}", {val});'


def write_user_js(account: Dict) -> None:
    profile_dir = account["profile_dir"]
    os.makedirs(profile_dir, exist_ok=True)
    proxy = account.get("proxy") or {}
    lines = []
    if proxy:
        lines.append(_user_pref("network.proxy.type", 1))
        lines.append(_user_pref("network.proxy.no_proxies_on", ""))
        if "http" in proxy:
            http = proxy["http"]
            lines.append(_user_pref("network.proxy.http", http["host"]))
            lines.append(_user_pref("network.proxy.http_port", http["port"]))
        if "https" in proxy:
            https = proxy["https"]
            lines.append(_user_pref("network.proxy.ssl", https["host"]))
            lines.append(_user_pref("network.proxy.ssl_port", https["port"]))
        elif "http" in proxy:
            http = proxy["http"]
            lines.append(_user_pref("network.proxy.ssl", http["host"]))
            lines.append(_user_pref("network.proxy.ssl_port", http["port"]))
        if "socks5" in proxy:
            socks = proxy["socks5"]
            lines.append(_user_pref("network.proxy.socks", socks["host"]))
            lines.append(_user_pref("network.proxy.socks_port", socks["port"]))
            lines.append(_user_pref("network.proxy.socks_version", 5))
            lines.append(_user_pref("network.proxy.socks_remote_dns", True))
    else:
        lines.append(_user_pref("network.proxy.type", 0))
        lines.append(_user_pref("network.proxy.no_proxies_on", ""))
    user_js_path = os.path.join(profile_dir, "user.js")
    with open(user_js_path, "w", encoding="utf-8") as f:
        f.write("// Generated by launcher, do not edit\n")
        for line in lines:
            f.write(line + "\n")


def ensure_profile(account: Dict) -> None:
    os.makedirs(account["profile_dir"], exist_ok=True)
    write_user_js(account)


def _log_file():
    os.makedirs(LOG_DIR, exist_ok=True)
    return open(LAUNCHER_LOG, "a", encoding="utf-8")


def is_running(profile_dir: str) -> bool:
    pattern = profile_dir
    result = subprocess.run(
        ["pgrep", "-f", pattern],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def start_account(account: Dict) -> Tuple[bool, str]:
    ensure_profile(account)
    if is_running(account["profile_dir"]):
        return False, "already_running"
    cmd = ["firefox-esr", "--no-remote", "--profile", account["profile_dir"]]
    if account.get("default_url"):
        cmd.append(account["default_url"])
    env = os.environ.copy()
    env["DISPLAY"] = DISPLAY
    log_handle = _log_file()
    subprocess.Popen(cmd, env=env, stdout=log_handle, stderr=log_handle)
    log.info("started firefox for %s", account["id"])
    return True, "started"


def stop_account(account: Dict) -> Tuple[bool, str]:
    if not is_running(account["profile_dir"]):
        return False, "already_stopped"
    pattern = account["profile_dir"]
    result = subprocess.run(
        ["pkill", "-f", pattern],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode == 0:
        log.info("stopped firefox for %s", account["id"])
        return True, "stopped"
    return False, "stop_failed"


def delete_profile_dir(path: str) -> None:
    if os.path.exists(path):
        shutil.rmtree(path, ignore_errors=True)
