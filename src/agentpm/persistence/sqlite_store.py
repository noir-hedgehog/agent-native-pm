from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional
from uuid import uuid4

from agentpm.store import AgentRun, AuditEvent, TaskSession


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_task_session(row: sqlite3.Row) -> TaskSession:
    return TaskSession(
        task_session_id=row["task_session_id"],
        project_id=row["project_id"],
        task_id=row["task_id"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_agent_run(row: sqlite3.Row) -> AgentRun:
    return AgentRun(
        agent_run_id=row["agent_run_id"],
        task_session_id=row["task_session_id"],
        stage_role=row["stage_role"],
        agent_provider=row["agent_provider"],
        agent_profile=row["agent_profile"],
        status=row["status"],
        retry_index=row["retry_index"],
        provider_session_id=row["provider_session_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class SqliteStore:
    """SQLite persistence backend for task sessions, agent runs, and audit events."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row

    def close(self) -> None:
        self._conn.close()

    def run_migrations(self) -> None:
        schema_statements: Iterable[str] = (
            """
            CREATE TABLE IF NOT EXISTS project_policy (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL UNIQUE,
                pipeline_definition TEXT NOT NULL,
                transition_approval_rules TEXT NOT NULL,
                transition_timeout_hours INTEGER NOT NULL,
                allowed_actions_by_role TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS task_session (
                task_session_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS idempotency_key (
                key TEXT PRIMARY KEY,
                task_session_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(task_session_id) REFERENCES task_session(task_session_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS agent_run (
                agent_run_id TEXT PRIMARY KEY,
                task_session_id TEXT NOT NULL,
                stage_role TEXT NOT NULL,
                agent_provider TEXT NOT NULL,
                agent_profile TEXT NOT NULL,
                status TEXT NOT NULL,
                retry_index INTEGER NOT NULL,
                provider_session_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(task_session_id) REFERENCES task_session(task_session_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS handoff_contract (
                id TEXT PRIMARY KEY,
                agent_run_id TEXT NOT NULL,
                goal TEXT,
                completed TEXT,
                evidence TEXT,
                risks TEXT,
                next_actions TEXT,
                confidence TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(agent_run_id) REFERENCES agent_run(agent_run_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS transition_approval (
                id TEXT PRIMARY KEY,
                task_session_id TEXT NOT NULL,
                from_run_id TEXT NOT NULL,
                to_stage_role TEXT NOT NULL,
                status TEXT NOT NULL,
                reviewer_id TEXT,
                decision_note TEXT,
                created_at TEXT NOT NULL,
                resolved_at TEXT,
                FOREIGN KEY(task_session_id) REFERENCES task_session(task_session_id),
                FOREIGN KEY(from_run_id) REFERENCES agent_run(agent_run_id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS audit_event (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                task_session_id TEXT NOT NULL,
                agent_run_id TEXT,
                event_type TEXT NOT NULL,
                event_payload TEXT NOT NULL,
                occurred_at TEXT NOT NULL
            )
            """,
        )

        with self._conn:
            for statement in schema_statements:
                self._conn.execute(statement)

    def get_or_create_session(self, idempotency_key: str, project_id: str, task_id: str) -> tuple[TaskSession, bool]:
        existing = self._conn.execute(
            "SELECT task_session_id FROM idempotency_key WHERE key = ?",
            (idempotency_key,),
        ).fetchone()

        if existing:
            row = self._conn.execute(
                "SELECT * FROM task_session WHERE task_session_id = ?",
                (existing["task_session_id"],),
            ).fetchone()
            return _row_to_task_session(row), True

        now = _utc_now_iso()
        task_session_id = f"ts_{uuid4().hex[:12]}"
        with self._conn:
            self._conn.execute(
                "INSERT INTO task_session (task_session_id, project_id, task_id, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (task_session_id, project_id, task_id, "in_progress", now, now),
            )
            self._conn.execute(
                "INSERT INTO idempotency_key (key, task_session_id, project_id, task_id, created_at) VALUES (?, ?, ?, ?, ?)",
                (idempotency_key, task_session_id, project_id, task_id, now),
            )

        row = self._conn.execute(
            "SELECT * FROM task_session WHERE task_session_id = ?",
            (task_session_id,),
        ).fetchone()
        return _row_to_task_session(row), False

    def get_task_session(self, task_session_id: str) -> Optional[TaskSession]:
        row = self._conn.execute(
            "SELECT * FROM task_session WHERE task_session_id = ?",
            (task_session_id,),
        ).fetchone()
        return _row_to_task_session(row) if row else None

    def update_task_session_status(self, task_session_id: str, status: str) -> TaskSession:
        now = _utc_now_iso()
        with self._conn:
            self._conn.execute(
                "UPDATE task_session SET status = ?, updated_at = ? WHERE task_session_id = ?",
                (status, now, task_session_id),
            )

        row = self._conn.execute(
            "SELECT * FROM task_session WHERE task_session_id = ?",
            (task_session_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown task_session_id: {task_session_id}")
        return _row_to_task_session(row)

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
        now = _utc_now_iso()
        agent_run_id = f"ar_{uuid4().hex[:12]}"
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO agent_run (
                    agent_run_id, task_session_id, stage_role, agent_provider, agent_profile,
                    status, retry_index, provider_session_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    agent_run_id,
                    task_session_id,
                    stage_role,
                    agent_provider,
                    agent_profile,
                    status,
                    retry_index,
                    provider_session_id,
                    now,
                    now,
                ),
            )

        row = self._conn.execute(
            "SELECT * FROM agent_run WHERE agent_run_id = ?",
            (agent_run_id,),
        ).fetchone()
        return _row_to_agent_run(row)

    def get_agent_run(self, agent_run_id: str) -> Optional[AgentRun]:
        row = self._conn.execute(
            "SELECT * FROM agent_run WHERE agent_run_id = ?",
            (agent_run_id,),
        ).fetchone()
        return _row_to_agent_run(row) if row else None

    def transition_agent_run(self, agent_run_id: str, to_status: str) -> AgentRun:
        row = self._conn.execute(
            "SELECT * FROM agent_run WHERE agent_run_id = ?",
            (agent_run_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown agent_run_id: {agent_run_id}")

        current = row["status"]
        self._validate_agent_run_transition(current, to_status)
        now = _utc_now_iso()

        with self._conn:
            self._conn.execute(
                "UPDATE agent_run SET status = ?, updated_at = ? WHERE agent_run_id = ?",
                (to_status, now, agent_run_id),
            )

        updated = self._conn.execute(
            "SELECT * FROM agent_run WHERE agent_run_id = ?",
            (agent_run_id,),
        ).fetchone()
        return _row_to_agent_run(updated)

    def add_audit_event(self, event: AuditEvent) -> None:
        event_id = f"ae_{uuid4().hex[:12]}"
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO audit_event (
                    id, project_id, task_id, task_session_id, agent_run_id,
                    event_type, event_payload, occurred_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    self._project_id_for_session(event.task_session_id),
                    event.task_id,
                    event.task_session_id,
                    None,
                    event.event_type,
                    json.dumps(event.payload, ensure_ascii=True),
                    event.occurred_at,
                ),
            )

    def list_audit_events(self) -> list[AuditEvent]:
        rows = self._conn.execute(
            "SELECT event_type, task_id, task_session_id, event_payload, occurred_at FROM audit_event ORDER BY occurred_at ASC"
        ).fetchall()
        return [
            AuditEvent(
                event_type=row["event_type"],
                task_id=row["task_id"],
                task_session_id=row["task_session_id"],
                payload=json.loads(row["event_payload"]),
                occurred_at=row["occurred_at"],
            )
            for row in rows
        ]

    def _project_id_for_session(self, task_session_id: str) -> str:
        row = self._conn.execute(
            "SELECT project_id FROM task_session WHERE task_session_id = ?",
            (task_session_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"unknown task_session_id: {task_session_id}")
        return row["project_id"]

    @staticmethod
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
