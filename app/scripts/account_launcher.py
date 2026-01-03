#!/usr/bin/env python3
import argparse
import sys

sys.path.append("/app")
from common import accounts  # noqa: E402


def start(account_id: str) -> int:
    items = accounts.load_accounts()
    acc = accounts.find_account(items, account_id)
    if not acc:
        print(f"account {account_id} not found", file=sys.stderr)
        return 1
    started, status = accounts.start_account(acc)
    print(status)
    return 0 if started or status == "already_running" else 1


def stop(account_id: str) -> int:
    items = accounts.load_accounts()
    acc = accounts.find_account(items, account_id)
    if not acc:
        print(f"account {account_id} not found", file=sys.stderr)
        return 1
    stopped, status = accounts.stop_account(acc)
    print(status)
    return 0 if stopped or status == "already_stopped" else 1


def main():
    parser = argparse.ArgumentParser(description="Start or stop an account browser")
    parser.add_argument("action", choices=["start", "stop"])
    parser.add_argument("account_id")
    args = parser.parse_args()
    if args.action == "start":
        return start(args.account_id)
    return stop(args.account_id)


if __name__ == "__main__":
    sys.exit(main())
