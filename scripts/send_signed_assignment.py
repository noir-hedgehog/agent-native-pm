#!/usr/bin/env python3
import argparse
import hashlib
import hmac
import json
import urllib.request


def sign(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return digest


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
        "event": "issue",
        "action": "update",
        "webhook_id": "wh_local_001",
        "workspace_id": "ws_local",
        "data": {
            "id": args.task_id,
            "project_id": args.project_id,
            "identifier": "AG-LOCAL",
            "title": "Local webhook smoke",
            "description_text": "Validate assignment webhook end-to-end",
            "assignees": [{"id": args.assignee}],
            "updated_by": "user_local",
        },
    }

    raw = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        args.url,
        data=raw,
        headers={
            "Content-Type": "application/json",
            "X-Plane-Signature": sign(raw, args.secret),
            "X-Plane-Delivery": args.event_id,
            "X-Plane-Event": "issue",
        },
        method="POST",
    )

    with urllib.request.urlopen(req) as resp:  # nosec B310
        body = resp.read().decode("utf-8")
        print(resp.status)
        print(body)


if __name__ == "__main__":
    main()
