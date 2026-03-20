from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Protocol


class OpenClawTransport(Protocol):
    def post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        ...

    def get(self, path: str) -> Dict[str, Any]:
        ...


@dataclass
class AdapterRunStartResult:
    provider: str
    provider_run_id: str
    provider_session_id: str
    status: str
    started_at: Optional[str]


class HttpOpenClawTransport:
    def __init__(self, base_url: str, token: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _request(self, method: str, path: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
        body = None
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url=f"{self.base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        with urllib.request.urlopen(req) as response:  # nosec B310 - controlled URL from config
            data = response.read().decode("utf-8")
            return json.loads(data) if data else {}

    def post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("POST", path, payload)

    def get(self, path: str) -> Dict[str, Any]:
        return self._request("GET", path)


class OpenClawAdapter:
    """Normalizes OpenClaw run lifecycle to orchestrator contract."""

    _status_map = {
        "queued": "queued",
        "pending": "queued",
        "running": "running",
        "in_progress": "running",
        "completed": "succeeded",
        "succeeded": "succeeded",
        "failed": "failed",
        "error": "failed",
        "canceled": "canceled",
        "cancelled": "canceled",
    }

    def __init__(self, transport: OpenClawTransport) -> None:
        self.transport = transport

    @classmethod
    def normalize_status(cls, provider_status: str) -> str:
        return cls._status_map.get(provider_status.lower(), "failed")

    def start_run(self, payload: Dict[str, Any]) -> AdapterRunStartResult:
        provider_payload = {
            "instruction": payload["instruction"],
            "context": payload.get("context", {}),
            "metadata": {
                "task_session_id": payload["task_session_id"],
                "agent_run_id": payload["agent_run_id"],
                "task_id": payload["task_id"],
                "stage_role": payload["stage_role"],
            },
            "policy": payload.get("policy", {}),
        }
        response = self.transport.post("/runs", provider_payload)
        return AdapterRunStartResult(
            provider="openclaw",
            provider_run_id=response["run_id"],
            provider_session_id=response["session_id"],
            status=self.normalize_status(response.get("status", "queued")),
            started_at=response.get("started_at"),
        )

    def send_message(self, provider_run_id: str, content: str, role: str = "system") -> Dict[str, Any]:
        response = self.transport.post(
            f"/runs/{provider_run_id}/messages",
            {"role": role, "content": content},
        )
        return {
            "accepted": bool(response.get("accepted", True)),
            "queued_at": response.get("queued_at"),
        }

    def get_run(self, provider_run_id: str) -> Dict[str, Any]:
        response = self.transport.get(f"/runs/{provider_run_id}")
        return {
            "provider": "openclaw",
            "provider_run_id": response["run_id"],
            "provider_session_id": response["session_id"],
            "status": self.normalize_status(response.get("status", "failed")),
            "progress": response.get("progress", {}),
            "updated_at": response.get("updated_at"),
        }

    def cancel_run(self, provider_run_id: str) -> Dict[str, Any]:
        response = self.transport.post(f"/runs/{provider_run_id}/cancel", {})
        return {
            "status": self.normalize_status(response.get("status", "canceled")),
            "canceled_at": response.get("canceled_at"),
        }

    def stream_events(self, provider_run_id: str) -> List[Dict[str, Any]]:
        response = self.transport.get(f"/runs/{provider_run_id}/events")
        events: Iterable[Dict[str, Any]] = response.get("events", [])
        return [self._normalize_event(provider_run_id, event) for event in events]

    def _normalize_event(self, provider_run_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
        provider_type = event.get("type", "run.output")
        normalized_type = self._map_event_type(provider_type)
        return {
            "event_id": event.get("id"),
            "provider": "openclaw",
            "provider_run_id": provider_run_id,
            "provider_session_id": event.get("session_id"),
            "type": normalized_type,
            "occurred_at": event.get("occurred_at"),
            "payload": event.get("payload", {}),
        }

    @staticmethod
    def _map_event_type(provider_type: str) -> str:
        mapping = {
            "run.started": "run.started",
            "run.progress": "run.progress",
            "run.output": "run.output",
            "run.completed": "run.completed",
            "run.failed": "run.failed",
            "run.canceled": "run.canceled",
            "message": "run.output",
            "completed": "run.completed",
            "failed": "run.failed",
        }
        return mapping.get(provider_type, "run.output")
