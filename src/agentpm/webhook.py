from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Mapping

from .errors import InvalidPayloadError
from .signature import SIGNATURE_HEADER, verify_signature
from .store import AuditEvent, InMemoryStore


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require(payload: Dict[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise InvalidPayloadError(f"missing required field: {path}")
        current = current[part]
    return current


def normalize_assignment_event(payload: Dict[str, Any]) -> Dict[str, Any]:
    event_id = _require(payload, "event_id")
    event_type = _require(payload, "event_type")
    project_id = _require(payload, "project.id")
    task_id = _require(payload, "task.id")

    if event_type != "task.assigned":
        raise InvalidPayloadError("unsupported event_type, expected task.assigned")

    return {
        "event_id": event_id,
        "project_id": project_id,
        "task_id": task_id,
        "task_key": payload.get("task", {}).get("key"),
        "assignee_id": payload.get("assignee", {}).get("id"),
        "occurred_at": payload.get("occurred_at"),
        "actor_id": payload.get("actor", {}).get("id"),
    }


def make_idempotency_key(event: Dict[str, Any]) -> str:
    return f"{event['event_id']}:{event['task_id']}"


def handle_assignment_webhook(
    *,
    raw_body: bytes,
    headers: Mapping[str, str],
    secret: str,
    store: InMemoryStore,
) -> tuple[int, Dict[str, Any]]:
    normalized_headers = {k.lower(): v for k, v in headers.items()}
    provided_sig = normalized_headers.get(SIGNATURE_HEADER, "")
    verify_signature(raw_body, provided_sig, secret)

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise InvalidPayloadError("body is not valid JSON") from exc

    event = normalize_assignment_event(payload)
    idempotency_key = make_idempotency_key(event)
    session, duplicate = store.get_or_create_session(idempotency_key, event["project_id"], event["task_id"])

    store.add_audit_event(
        AuditEvent(
            event_type="webhook.assignment.accepted",
            task_id=event["task_id"],
            task_session_id=session.task_session_id,
            payload={
                "idempotency_key": idempotency_key,
                "duplicate": duplicate,
                "event_id": event["event_id"],
            },
            occurred_at=_utc_now_iso(),
        )
    )

    return (
        202,
        {
            "accepted": True,
            "duplicate": duplicate,
            "task_session_id": session.task_session_id,
            "idempotency_key": idempotency_key,
        },
    )
