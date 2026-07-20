from __future__ import annotations

import json
import hmac
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Tuple
from urllib.parse import urlparse

from .errors import InvalidPayloadError, InvalidSignatureError
from .policy import policy_input_from_payload
from .reporting import ReportingService
from .runtime import build_assignment_orchestrator_from_env, build_store_from_env
from .store import InMemoryStore


class AssignmentWebhookHandler(BaseHTTPRequestHandler):
    store = InMemoryStore()
    orchestrator = None

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", "0"))
        return self.rfile.read(length)

    def _write_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        origin = self.headers.get("Origin")
        allowed_origin = _allowed_origin(origin)
        if allowed_origin:
            self.send_header("Access-Control-Allow-Origin", allowed_origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Plane-Signature")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        _log(
            "http_request",
            method=self.command,
            path=self.path,
            client=self.client_address[0],
            message=format % args,
        )

    def _error(self, status: int, code: str, message: str) -> Tuple[int, dict]:
        return status, {"error": {"code": code, "message": message}}

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/approvals/") and path.endswith("/decision"):
            if not _admin_authorized(self.headers.get("X-AgentPM-Admin-Token")):
                status, payload = self._error(403, "FORBIDDEN", "valid AgentPM admin token required")
                self._write_json(status, payload)
                return
            approval_id = path.removeprefix("/approvals/").removesuffix("/decision").strip("/")
            try:
                request_payload = json.loads(self._read_body().decode("utf-8") or "{}")
                orchestrator = self.orchestrator or build_assignment_orchestrator_from_env(self.store)
                payload = orchestrator.record_transition_decision(
                    approval_id=approval_id,
                    decision=str(request_payload.get("decision") or ""),
                    reviewer_id=str(request_payload.get("reviewer_id") or "plane-admin"),
                    note=request_payload.get("note"),
                )
                if payload.get("resume_queued"):
                    threading.Thread(
                        target=_resume_approval_in_background,
                        args=(orchestrator, approval_id),
                        daemon=True,
                        name=f"approval-{approval_id}",
                    ).start()
                self._write_json(202, payload)
                return
            except (KeyError, ValueError) as exc:
                status, payload = self._error(400, "INVALID_APPROVAL_DECISION", str(exc))
            except Exception as exc:
                status, payload = self._error(500, "INTERNAL_ERROR", str(exc))
            self._write_json(status, payload)
            return

        if path.startswith("/policies/projects/"):
            if not _admin_authorized(self.headers.get("X-AgentPM-Admin-Token")):
                status, payload = self._error(403, "FORBIDDEN", "valid AgentPM admin token required")
                self._write_json(status, payload)
                return
            project_id = path.removeprefix("/policies/projects/").strip("/")
            if not project_id or "/" in project_id:
                status, payload = self._error(404, "NOT_FOUND", "unknown endpoint")
                self._write_json(status, payload)
                return
            try:
                raw_body = self._read_body()
                request_payload = json.loads(raw_body.decode("utf-8") or "{}")
                policy = policy_input_from_payload(project_id, request_payload)
                published = self.store.publish_project_policy(policy)
                self._write_json(201, {"policy": published.public_dict})
                return
            except ValueError as exc:
                status, payload = self._error(400, "INVALID_POLICY", str(exc))
            except Exception as exc:
                status, payload = self._error(500, "INTERNAL_ERROR", str(exc))
            self._write_json(status, payload)
            return

        if self.path != "/webhooks/plane/assignment":
            status, payload = self._error(404, "NOT_FOUND", "unknown endpoint")
            self._write_json(status, payload)
            return

        raw_body = self._read_body()
        try:
            orchestrator = self.orchestrator or build_assignment_orchestrator_from_env(self.store)
            if _env_bool("AGENTPM_ASYNC_WEBHOOK", False):
                payload, plane_payload, event = orchestrator.accept_assignment(raw_body=raw_body, headers=self.headers)
                if plane_payload is not None and event is not None:
                    threading.Thread(
                        target=_process_assignment_in_background,
                        args=(orchestrator, payload, plane_payload, event),
                        daemon=True,
                        name=f"assignment-{payload['task_session_id']}",
                    ).start()
            else:
                payload = orchestrator.process_assignment(raw_body=raw_body, headers=self.headers)
            self._write_json(202, payload)
            return
        except InvalidSignatureError as exc:
            status, payload = self._error(401, "INVALID_SIGNATURE", str(exc))
        except InvalidPayloadError as exc:
            status, payload = self._error(400, "INVALID_PAYLOAD", str(exc))
        except Exception as exc:
            status, payload = self._error(500, "INTERNAL_ERROR", str(exc))

        self._write_json(status, payload)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        reporting = ReportingService(self.store)

        if path == "/health":
            self._write_json(
                200,
                {
                    "status": "ok",
                    "service": "agentpm",
                    "version": _version(),
                    "store": os.environ.get("AGENTPM_STORE", "memory").lower(),
                    "agent_provider": os.environ.get("AGENTPM_AGENT_PROVIDER", "dev").lower(),
                },
            )
            return

        if path.startswith("/policies/projects/"):
            suffix = path.removeprefix("/policies/projects/").strip("/")
            if suffix.endswith("/history"):
                project_id = suffix.removesuffix("/history").strip("/")
                versions = self.store.list_project_policy_versions(project_id)
                self._write_json(200, {"policies": [policy.public_dict for policy in versions]})
                return
            project_id = suffix
            policy = self.store.get_latest_project_policy(project_id)
            if not policy:
                self._write_json(404, {"error": {"code": "POLICY_NOT_FOUND", "message": "project policy not found"}})
                return
            self._write_json(200, {"policy": policy.public_dict})
            return

        if path.startswith("/metrics/projects/"):
            project_id = path.removeprefix("/metrics/projects/")
            self._write_json(200, reporting.get_project_metrics(project_id))
            return

        if path.startswith("/runtime/projects/"):
            project_id = path.removeprefix("/runtime/projects/").strip("/")
            sessions = [session for session in self.store.list_task_sessions() if session.project_id == project_id]
            sessions.sort(key=lambda item: item.updated_at, reverse=True)
            pending_by_session = {
                approval.task_session_id: approval for approval in self.store.list_pending_transition_approvals()
            }
            self._write_json(
                200,
                {
                    "project_id": project_id,
                    "sessions": [
                        {
                            "task_session_id": session.task_session_id,
                            "task_id": session.task_id,
                            "status": session.status,
                            "created_at": session.created_at,
                            "updated_at": session.updated_at,
                            "runs": [run.__dict__ for run in self.store.list_agent_runs_for_session(session.task_session_id)],
                            "pending_approval": (
                                pending_by_session[session.task_session_id].__dict__
                                if session.task_session_id in pending_by_session
                                else None
                            ),
                        }
                        for session in sessions[:50]
                    ],
                },
            )
            return

        if path.startswith("/tasks/") and path.endswith("/timeline"):
            task_id = path.split("/")[2]
            self._write_json(200, reporting.get_task_timeline(task_id))
            return

        status, payload = self._error(404, "NOT_FOUND", "unknown endpoint")
        self._write_json(status, payload)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._write_json(204, {})


def run_server() -> None:
    port = int(os.environ.get("PORT", "8080"))
    host = os.environ.get("HOST", "127.0.0.1")
    AssignmentWebhookHandler.store = build_store_from_env()
    AssignmentWebhookHandler.orchestrator = build_assignment_orchestrator_from_env(AssignmentWebhookHandler.store)
    server = ThreadingHTTPServer((host, port), AssignmentWebhookHandler)
    _log("server_started", host=host, port=port, version=_version())
    server.serve_forever()


def _allowed_origin(origin: str | None) -> str | None:
    configured = os.environ.get("AGENTPM_ALLOWED_ORIGINS", "http://127.0.0.1,http://localhost")
    allowed = {item.strip().rstrip("/") for item in configured.split(",") if item.strip()}
    if "*" in allowed:
        return "*"
    normalized = (origin or "").rstrip("/")
    return origin if normalized in allowed else None


def _version() -> str:
    configured = os.environ.get("AGENTPM_VERSION")
    if configured:
        return configured
    version_file = Path(__file__).resolve().parents[2] / "VERSION"
    try:
        return version_file.read_text(encoding="utf-8").strip()
    except OSError:
        return "dev"


def _log(event: str, **fields) -> None:
    payload = {"event": event, **fields}
    if os.environ.get("AGENTPM_LOG_FORMAT", "text").lower() == "json":
        print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)
    else:
        message = " ".join(f"{key}={value}" for key, value in payload.items())
        print(message, file=sys.stdout, flush=True)


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _process_assignment_in_background(orchestrator, receipt: dict, payload: dict, event: dict) -> None:
    try:
        result = orchestrator.process_accepted_assignment(receipt=receipt, payload=payload, event=event)
        _log(
            "assignment_completed",
            task_session_id=receipt["task_session_id"],
            task_id=event.get("task_id"),
            completed=result.get("completed"),
            awaiting_approval=result.get("awaiting_approval"),
        )
    except Exception as exc:
        _log(
            "assignment_failed",
            task_session_id=receipt.get("task_session_id"),
            task_id=event.get("task_id"),
            error_type=type(exc).__name__,
            message=str(exc),
        )


def _resume_approval_in_background(orchestrator, approval_id: str) -> None:
    try:
        result = orchestrator.resume_approved_transition(approval_id)
        _log(
            "approval_resume_completed",
            approval_id=approval_id,
            completed=result.get("completed"),
            awaiting_approval=result.get("awaiting_approval"),
        )
    except Exception as exc:
        _log(
            "approval_resume_failed",
            approval_id=approval_id,
            error_type=type(exc).__name__,
            message=str(exc),
        )


def _admin_authorized(provided: str | None) -> bool:
    expected = os.environ.get("AGENTPM_ADMIN_TOKEN")
    if not expected:
        return True
    return bool(provided) and hmac.compare_digest(provided, expected)


if __name__ == "__main__":
    run_server()
