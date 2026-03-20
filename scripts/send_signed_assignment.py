#!/usr/bin/env python3
import argparse
import hashlib
import hmac
import json
import urllib.request


def sign(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Send signed Plane assignment webhook")
    parser.add_argument("--url", default="http://127.0.0.1:8080/webhooks/plane/assignment")
    parser.add_argument("--secret", default="dev-secret")
    parser.add_argument("--event-id", default="plane_evt_local_001")
    parser.add_argument("--task-id", default="task_local_001")
    parser.add_argument("--project-id", default="proj_local")
    parser.add_argument("--assignee", default="agent_openclaw_coder")
    args = parser.parse_args()

    payload = {
        "event_id": args.event_id,
        "event_type": "task.assigned",
        "occurred_at": "2026-03-20T00:00:00Z",
        "project": {"id": args.project_id, "name": "Local Project"},
        "task": {
            "id": args.task_id,
            "key": "AG-LOCAL",
            "title": "Local webhook smoke",
            "description": "Validate assignment webhook end-to-end",
            "status": "todo",
        },
        "assignee": {"id": args.assignee, "type": "agent_profile"},
        "actor": {"id": "user_local", "name": "Local Operator"},
    }

    raw = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        args.url,
        data=raw,
        headers={
            "Content-Type": "application/json",
            "X-Plane-Signature": sign(raw, args.secret),
        },
        method="POST",
    )

    with urllib.request.urlopen(req) as resp:  # nosec B310
        body = resp.read().decode("utf-8")
        print(resp.status)
        print(body)


if __name__ == "__main__":
    main()
