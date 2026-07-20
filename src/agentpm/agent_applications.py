from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from .agent_accounts import DEFAULT_AGENT_APPLICATIONS_FILE, default_agent_email, normalize_agent_id, normalize_role


ACTIVE_APPLICATION_STATUSES = {"pending"}


@dataclass(frozen=True)
class AgentApplication:
    application_id: str
    agent_id: str
    display_name: str
    email: str
    requested_role: str
    reason: str
    project_id: str | None
    status: str
    created_at: str
    updated_at: str
    source: str = "bootstrap"
    decision_reason: str | None = None

    @property
    def public_dict(self) -> dict[str, Any]:
        return {
            "application_id": self.application_id,
            "agent_id": self.agent_id,
            "display_name": self.display_name,
            "email": self.email,
            "requested_role": self.requested_role,
            "reason": self.reason,
            "project_id": self.project_id,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source": self.source,
            "decision_reason": self.decision_reason,
        }


class AgentApplicationStore:
    def __init__(self, path: str | Path | None = None, *, env: Mapping[str, str] | None = None) -> None:
        self.path = _applications_path(path, env=env)

    def list(self, *, status: str | None = None) -> list[AgentApplication]:
        applications = [_application_from_row(row) for row in self._read().get("applications", [])]
        if status:
            applications = [application for application in applications if application.status == status]
        return sorted(applications, key=lambda application: application.created_at)

    def request_registration(
        self,
        *,
        agent_id: str,
        display_name: str,
        email: str | None = None,
        requested_role: str = "member",
        reason: str = "",
        project_id: str | None = None,
        source: str = "bootstrap",
    ) -> dict[str, Any]:
        normalized_agent_id = normalize_agent_id(agent_id)
        if not normalized_agent_id:
            raise ValueError("agent_id is required")
        if not display_name.strip():
            raise ValueError("display_name is required")
        role = normalize_role(requested_role)
        payload = self._read()
        applications = payload.setdefault("applications", [])
        for row in applications:
            if (
                row.get("agent_id") == normalized_agent_id
                and row.get("project_id") == project_id
                and row.get("status") in ACTIVE_APPLICATION_STATUSES
            ):
                return {"application": _application_from_row(row).public_dict, "created": False}

        now = _now()
        row = {
            "application_id": f"app-{uuid4()}",
            "agent_id": normalized_agent_id,
            "display_name": display_name.strip(),
            "email": email or default_agent_email(normalized_agent_id),
            "requested_role": role,
            "reason": reason,
            "project_id": project_id,
            "status": "pending",
            "created_at": now,
            "updated_at": now,
            "source": source,
        }
        applications.append(row)
        self._write(payload)
        return {"application": _application_from_row(row).public_dict, "created": True}

    def mark(self, application_id: str, *, status: str, decision_reason: str | None = None) -> AgentApplication:
        payload = self._read()
        for row in payload.setdefault("applications", []):
            if row.get("application_id") == application_id:
                row["status"] = status
                row["decision_reason"] = decision_reason
                row["updated_at"] = _now()
                self._write(payload)
                return _application_from_row(row)
        raise ValueError(f"unknown application_id: {application_id}")

    def get(self, application_id: str) -> AgentApplication:
        for application in self.list():
            if application.application_id == application_id:
                return application
        raise ValueError(f"unknown application_id: {application_id}")

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"applications": []}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{self.path} must contain valid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"{self.path} must contain a JSON object")
        payload.setdefault("applications", [])
        return payload

    def _write(self, payload: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.path.chmod(0o600)


def _application_from_row(row: Mapping[str, Any]) -> AgentApplication:
    agent_id = normalize_agent_id(str(row.get("agent_id") or ""))
    return AgentApplication(
        application_id=str(row.get("application_id") or row.get("id") or ""),
        agent_id=agent_id,
        display_name=str(row.get("display_name") or row.get("name") or agent_id),
        email=str(row.get("email") or default_agent_email(agent_id)),
        requested_role=normalize_role(str(row.get("requested_role") or row.get("role") or "member")),
        reason=str(row.get("reason") or ""),
        project_id=str(row["project_id"]) if row.get("project_id") else None,
        status=str(row.get("status") or "pending"),
        created_at=str(row.get("created_at") or _now()),
        updated_at=str(row.get("updated_at") or row.get("created_at") or _now()),
        source=str(row.get("source") or "bootstrap"),
        decision_reason=str(row["decision_reason"]) if row.get("decision_reason") else None,
    )


def _applications_path(path: str | Path | None = None, *, env: Mapping[str, str] | None = None) -> Path:
    values = os.environ if env is None else env
    raw = path or values.get("AGENTPM_PLANE_AGENT_APPLICATIONS_FILE") or DEFAULT_AGENT_APPLICATIONS_FILE
    return Path(raw)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
