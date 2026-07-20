from __future__ import annotations

import json
import time

from .approval import ApprovalService
from .env import mesh_env
from .runtime import build_store_from_env


def run_once() -> dict[str, list[str]]:
    store = build_store_from_env()
    try:
        result = ApprovalService(store).evaluate_timeouts(
            reminder_after_hours=int(str(mesh_env("APPROVAL_REMINDER_HOURS", "24"))),
            block_after_hours=int(str(mesh_env("APPROVAL_BLOCK_HOURS", "72"))),
        )
        print(json.dumps({"event": "approval_timeout_scan", **result}), flush=True)
        return result
    finally:
        close = getattr(store, "close", None)
        if close:
            close()


def run_worker() -> None:
    poll_seconds = max(10, int(str(mesh_env("TIMEOUT_POLL_SECONDS", "300"))))
    while True:
        try:
            run_once()
        except Exception as exc:
            print(json.dumps({"event": "approval_timeout_scan_failed", "error": str(exc)}), flush=True)
        time.sleep(poll_seconds)


if __name__ == "__main__":
    run_worker()
