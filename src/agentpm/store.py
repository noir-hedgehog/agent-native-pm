from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Protocol, Tuple
from uuid import uuid4


@dataclass
class TaskSession:
    task_session_id: str
    project_id: str
    task_id: str
    status: str
    created_at: str
    updated_at: str


@dataclass
class AgentRun:
    agent_run_id: str
    task_session_id: str
    stage_role: str
    agent_provider: str
    agent_profile: str
    status: str
    retry_index: int
    provider_session_id: str | None
    created_at: str
    updated_at: str


@dataclass
class AuditEvent:
    event_type: str
    task_id: str
    task_session_id: str
    payload: dict
    occurred_at: str


class Store(Protocol):
    def get_or_create_session(self, idempotency_key: str, project_id: str, task_id: str) -> Tuple[TaskSession, bool]:
        ...

    def add_audit_event(self, event: AuditEvent) -> None:
        ...


class InMemoryStore:
    """MVP in-memory persistence for dedupe, sessions, and audit events."""

    def __init__(self) -> None:
        self._sessions_by_key: Dict[str, TaskSession] = {}
        self._sessions_by_id: Dict[str, TaskSession] = {}
        self._agent_runs_by_id: Dict[str, AgentRun] = {}
        self._audit_events: List[AuditEvent] = []

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def get_or_create_session(self, idempotency_key: str, project_id: str, task_id: str) -> tuple[TaskSession, bool]:
        existing = self._sessions_by_key.get(idempotency_key)
        if existing:
            return existing, True

        now = self._now_iso()
        session = TaskSession(
            task_session_id=f"ts_{uuid4().hex[:12]}",
            project_id=project_id,
            task_id=task_id,
            status="in_progress",
            created_at=now,
            updated_at=now,
        )
        self._sessions_by_key[idempotency_key] = session
        self._sessions_by_id[session.task_session_id] = session
        return session, False

    def get_task_session(self, task_session_id: str) -> TaskSession | None:
        return self._sessions_by_id.get(task_session_id)

    def update_task_session_status(self, task_session_id: str, status: str) -> TaskSession:
        session = self._sessions_by_id[task_session_id]
        updated = TaskSession(
            task_session_id=session.task_session_id,
            project_id=session.project_id,
            task_id=session.task_id,
            status=status,
            created_at=session.created_at,
            updated_at=self._now_iso(),
        )
        self._sessions_by_id[task_session_id] = updated

        for key, value in self._sessions_by_key.items():
            if value.task_session_id == task_session_id:
                self._sessions_by_key[key] = updated
                break

        return updated

    def create_agent_run(
        self,
        *,
        task_session_id: str,
        stage_role: str,
        agent_provider: str,
        agent_profile: str,
        status: str = "queued",
        retry_index: int = 0,
        provider_session_id: str | None = None,
    ) -> AgentRun:
        now = self._now_iso()
        run = AgentRun(
            agent_run_id=f"ar_{uuid4().hex[:12]}",
            task_session_id=task_session_id,
            stage_role=stage_role,
            agent_provider=agent_provider,
            agent_profile=agent_profile,
            status=status,
            retry_index=retry_index,
            provider_session_id=provider_session_id,
            created_at=now,
            updated_at=now,
        )
        self._agent_runs_by_id[run.agent_run_id] = run
        return run

    def get_agent_run(self, agent_run_id: str) -> AgentRun | None:
        return self._agent_runs_by_id.get(agent_run_id)

    def transition_agent_run(self, agent_run_id: str, to_status: str) -> AgentRun:
        run = self._agent_runs_by_id[agent_run_id]
        _validate_agent_run_transition(run.status, to_status)
        updated = AgentRun(
            agent_run_id=run.agent_run_id,
            task_session_id=run.task_session_id,
            stage_role=run.stage_role,
            agent_provider=run.agent_provider,
            agent_profile=run.agent_profile,
            status=to_status,
            retry_index=run.retry_index,
            provider_session_id=run.provider_session_id,
            created_at=run.created_at,
            updated_at=self._now_iso(),
        )
        self._agent_runs_by_id[agent_run_id] = updated
        return updated

    def add_audit_event(self, event: AuditEvent) -> None:
        self._audit_events.append(event)

    def list_audit_events(self) -> List[AuditEvent]:
        return list(self._audit_events)


def _validate_agent_run_transition(from_status: str, to_status: str) -> None:
    allowed = {
        "queued": {"running", "canceled", "failed"},
        "running": {"succeeded", "failed", "canceled"},
        "failed": set(),
        "succeeded": set(),
        "canceled": set(),
    }
    if to_status not in allowed.get(from_status, set()):
        raise ValueError(f"invalid agent run transition: {from_status} -> {to_status}")
