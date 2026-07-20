#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_BASE_URL = os.environ.get("AGENTPM_BASE_URL", "http://127.0.0.1:8080").rstrip("/")


def main() -> None:
    parser = argparse.ArgumentParser(description="AgentPM project policy CLI")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    sub = parser.add_subparsers(dest="command", required=True)

    get_parser = sub.add_parser("get", help="Get latest project policy")
    get_parser.add_argument("project_id")

    history_parser = sub.add_parser("history", help="List project policy versions")
    history_parser.add_argument("project_id")

    publish_parser = sub.add_parser("publish", help="Publish a project policy from JSON")
    publish_parser.add_argument("project_id")
    publish_parser.add_argument("--file", required=True)

    args = parser.parse_args()

    if args.command == "get":
        result = _request("GET", f"{args.base_url}/policies/projects/{args.project_id}")
    elif args.command == "history":
        result = _request("GET", f"{args.base_url}/policies/projects/{args.project_id}/history")
    elif args.command == "publish":
        payload = json.loads(Path(args.file).read_text(encoding="utf-8"))
        result = _request("POST", f"{args.base_url}/policies/projects/{args.project_id}", payload)
    else:
        raise AssertionError(args.command)

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def _request(method: str, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url=url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request) as response:  # nosec B310 - configured local AgentPM URL
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        raise SystemExit(body)
    return json.loads(body) if body else {}


if __name__ == "__main__":
    main()
