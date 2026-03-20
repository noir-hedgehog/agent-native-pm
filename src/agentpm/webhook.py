from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Mapping

from .errors import InvalidPayloadError
from .signature import SIGNATURE_HEADER, verify_signature
from .store import AuditEvent, Store


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
    # Legacy internal payload shape.
    if "event_id" in payload and "event_type" in payload:
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

    # Plane webhook shape: event/action/webhook_id/workspace_id/data
    event = payload.get("event")
    action = payload.get("action")
    data = payload.get("data", {})
    if not isinstance(data, dict):
        raise InvalidPayloadError("invalid data field in plane webhook payload")

    if event != "issue":
        raise InvalidPayloadError("unsupported event, expected issue")
    if action not in {"create", "update"}:
        raise InvalidPayloadError("unsupported action, expected create or update")

    task_id = data.get("id")
    if not task_id:
        raise InvalidPayloadError("missing required field: data.id")

    project_id = (
        data.get("project_id")
        or data.get("project")
        or payload.get("workspace_id")
    )
    if not project_id:
        raise InvalidPayloadError("missing project/workspace identifier in webhook payload")

    assignee_id = _extract_assignee_id(data)
    return {
        "event_id": payload.get("delivery_id") or payload.get("webhook_id") or f"{event}:{action}:{task_id}",
        "project_id": project_id,
        "task_id": task_id,
        "task_key": data.get("identifier"),
        "assignee_id": assignee_id,
        "occurred_at": data.get("updated_at") or data.get("created_at"),
        "actor_id": data.get("updated_by") or data.get("created_by"),
    }


def _extract_assignee_id(data: Dict[str, Any]) -> Any:
    assignee = data.get("assignee")
    if isinstance(assignee, dict):
        return assignee.get("id")
    if isinstance(assignee, str):
        return assignee

    assignees = data.get("assignees")
    if isinstance(assignees, list) and assignees:
        first = assignees[0]
        if isinstance(first, dict):
            return first.get("id")
        if isinstance(first, str):
            return first

    assignee_ids = data.get("assignee_ids")
    if isinstance(assignee_ids, list) and assignee_ids:
        return assignee_ids[0]

    return None


def make_idempotency_key(event: Dict[str, Any]) -> str:
    return f"{event['event_id']}:{event['task_id']}"


def handle_assignment_webhook(
    *,
    raw_body: bytes,
    headers: Mapping[str, str],
    secret: str,
    store: Store,
) -> tuple[int, Dict[str, Any]]:
    normalized_headers = {k.lower(): v for k, v in headers.items()}
    provided_sig = normalized_headers.get(SIGNATURE_HEADER, "")
    verify_signature(raw_body, provided_sig, secret)

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise InvalidPayloadError("body is not valid JSON") from exc

    if "delivery_id" not in payload:
        payload["delivery_id"] = normalized_headers.get("x-plane-delivery")

    event = normalize_assignment_event(payload)
    if not event.get("assignee_id"):
        return (
            202,
            {
                "accepted": False,
                "ignored": True,
                "reason": "no_assignee",
                "event_id": event["event_id"],
            },
        )

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
