#!/usr/bin/env python3
import sys
import time

sys.path.append("/app")
from common import accounts  # noqa: E402


def main():
    items = accounts.load_accounts()
    started = []
    skipped = []
    for acc in items:
        if not acc.get("autostart"):
            continue
        ok, status = accounts.start_account(acc)
        if status == "started":
            started.append(acc["id"])
        else:
            skipped.append(acc["id"])
        time.sleep(0.2)
    if started or skipped:
        print(f"autostart: started={started} skipped={skipped}")


if __name__ == "__main__":
    main()
