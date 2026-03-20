from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List
from uuid import uuid4


@dataclass
class TaskSession:
    task_session_id: str
    project_id: str
    task_id: str
    status: str
    created_at: str


@dataclass
class AuditEvent:
    event_type: str
    task_id: str
    task_session_id: str
    payload: dict
    occurred_at: str


class InMemoryStore:
    """MVP in-memory persistence for dedupe, sessions, and audit events."""

    def __init__(self) -> None:
        self._sessions_by_key: Dict[str, TaskSession] = {}
        self._audit_events: List[AuditEvent] = []

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def get_or_create_session(self, idempotency_key: str, project_id: str, task_id: str) -> tuple[TaskSession, bool]:
        existing = self._sessions_by_key.get(idempotency_key)
        if existing:
            return existing, True

        session = TaskSession(
            task_session_id=f"ts_{uuid4().hex[:12]}",
            project_id=project_id,
            task_id=task_id,
            status="in_progress",
            created_at=self._now_iso(),
        )
        self._sessions_by_key[idempotency_key] = session
        return session, False

    def add_audit_event(self, event: AuditEvent) -> None:
        self._audit_events.append(event)

    def list_audit_events(self) -> List[AuditEvent]:
        return list(self._audit_events)
