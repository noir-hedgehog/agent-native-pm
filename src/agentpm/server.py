from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Tuple

from .errors import InvalidPayloadError, InvalidSignatureError
from .store import InMemoryStore
from .webhook import handle_assignment_webhook


class AssignmentWebhookHandler(BaseHTTPRequestHandler):
    store = InMemoryStore()
    secret = os.environ.get("PLANE_WEBHOOK_SECRET", "dev-secret")

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", "0"))
        return self.rfile.read(length)

    def _write_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status: int, code: str, message: str) -> Tuple[int, dict]:
        return status, {"error": {"code": code, "message": message}}

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/webhooks/plane/assignment":
            status, payload = self._error(404, "NOT_FOUND", "unknown endpoint")
            self._write_json(status, payload)
            return

        raw_body = self._read_body()
        try:
            status, payload = handle_assignment_webhook(
                raw_body=raw_body,
                headers=self.headers,
                secret=self.secret,
                store=self.store,
            )
            self._write_json(status, payload)
            return
        except InvalidSignatureError as exc:
            status, payload = self._error(401, "INVALID_SIGNATURE", str(exc))
        except InvalidPayloadError as exc:
            status, payload = self._error(400, "INVALID_PAYLOAD", str(exc))
        except Exception:
            status, payload = self._error(500, "INTERNAL_ERROR", "unexpected error")

        self._write_json(status, payload)


def run_server() -> None:
    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("127.0.0.1", port), AssignmentWebhookHandler)
    print(f"Listening on http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()
