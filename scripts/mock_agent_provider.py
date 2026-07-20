#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import urlparse


class MockAgentProviderHandler(BaseHTTPRequestHandler):
    runs: dict[str, dict[str, Any]] = {}

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _write_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/health":
            self._write_json(200, {"status": "OK"})
            return

        parts = [part for part in path.split("/") if part]
        if len(parts) == 2 and parts[0] == "runs":
            run = self.runs.get(parts[1])
            if not run:
                self._write_json(404, {"error": "unknown run"})
                return
            self._write_json(
                200,
                {
                    "run_id": parts[1],
                    "session_id": run["session_id"],
                    "status": "completed",
                    "progress": {"summary": "mock provider completed run", "percent": 100},
                    "updated_at": run["updated_at"],
                },
            )
            return

        if len(parts) == 3 and parts[0] == "runs" and parts[2] == "events":
            run = self.runs.get(parts[1])
            if not run:
                self._write_json(404, {"error": "unknown run"})
                return
            self._write_json(
                200,
                {
                    "events": [
                        {
                            "id": f"evt_{parts[1]}_progress",
                            "type": "run.progress",
                            "session_id": run["session_id"],
                            "occurred_at": run["updated_at"],
                            "payload": {"summary": "mock provider is working"},
                        },
                        {
                            "id": f"evt_{parts[1]}_completed",
                            "type": "run.completed",
                            "session_id": run["session_id"],
                            "occurred_at": run["updated_at"],
                            "payload": {
                                "handoff_hint": {
                                    "goal": "validate HTTP agent connector",
                                    "completed": ["started run", "streamed progress", "completed run"],
                                    "evidence": [parts[1]],
                                    "risks": [],
                                    "next_actions": ["swap mock URL for real provider URL"],
                                    "confidence": "high",
                                }
                            },
                        },
                    ]
                },
            )
            return

        self._write_json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/runs":
            payload = self._read_json()
            run_id = f"mock_run_{len(self.runs) + 1}"
            session_id = f"mock_session_{len(self.runs) + 1}"
            self.runs[run_id] = {
                "session_id": session_id,
                "payload": payload,
                "updated_at": "2026-06-25T00:00:00Z",
            }
            self._write_json(
                201,
                {
                    "run_id": run_id,
                    "session_id": session_id,
                    "status": "queued",
                    "started_at": "2026-06-25T00:00:00Z",
                },
            )
            return

        parts = [part for part in path.split("/") if part]
        if len(parts) == 3 and parts[0] == "runs" and parts[2] == "messages":
            self._write_json(202, {"accepted": True, "queued_at": "2026-06-25T00:00:00Z"})
            return
        if len(parts) == 3 and parts[0] == "runs" and parts[2] == "cancel":
            self._write_json(200, {"status": "canceled", "canceled_at": "2026-06-25T00:00:00Z"})
            return

        self._write_json(404, {"error": "not found"})


def main() -> None:
    port = int(os.environ.get("MOCK_AGENT_PROVIDER_PORT", "19090"))
    server = HTTPServer(("127.0.0.1", port), MockAgentProviderHandler)
    print(f"Mock agent provider listening on http://127.0.0.1:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
