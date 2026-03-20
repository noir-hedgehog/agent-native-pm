from __future__ import annotations

import json
import os
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


@dataclass
class OpenClawAdapterConfig:
    start_run_path: str = "/runs"
    send_message_path: str = "/runs/{provider_run_id}/messages"
    get_run_path: str = "/runs/{provider_run_id}"
    cancel_run_path: str = "/runs/{provider_run_id}/cancel"
    stream_events_path: str = "/runs/{provider_run_id}/events"
    run_id_key: str = "run_id"
    session_id_key: str = "session_id"
    status_key: str = "status"
    progress_key: str = "progress"
    events_key: str = "events"

    @classmethod
    def from_env(cls) -> "OpenClawAdapterConfig":
        return cls(
            start_run_path=os.environ.get("OPENCLAW_START_RUN_PATH", "/runs"),
            send_message_path=os.environ.get("OPENCLAW_SEND_MESSAGE_PATH", "/runs/{provider_run_id}/messages"),
            get_run_path=os.environ.get("OPENCLAW_GET_RUN_PATH", "/runs/{provider_run_id}"),
            cancel_run_path=os.environ.get("OPENCLAW_CANCEL_RUN_PATH", "/runs/{provider_run_id}/cancel"),
            stream_events_path=os.environ.get("OPENCLAW_STREAM_EVENTS_PATH", "/runs/{provider_run_id}/events"),
            run_id_key=os.environ.get("OPENCLAW_RUN_ID_KEY", "run_id"),
            session_id_key=os.environ.get("OPENCLAW_SESSION_ID_KEY", "session_id"),
            status_key=os.environ.get("OPENCLAW_STATUS_KEY", "status"),
            progress_key=os.environ.get("OPENCLAW_PROGRESS_KEY", "progress"),
            events_key=os.environ.get("OPENCLAW_EVENTS_KEY", "events"),
        )


class HttpOpenClawTransport:
    def __init__(self, base_url: str, token: str | None = None, api_key: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.api_key = api_key

    def _request(self, method: str, path: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
        body = None
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if self.api_key:
            headers["X-API-Key"] = self.api_key
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

    def __init__(self, transport: OpenClawTransport, config: OpenClawAdapterConfig | None = None) -> None:
        self.transport = transport
        self.config = config or OpenClawAdapterConfig()

    @classmethod
    def normalize_status(cls, provider_status: str) -> str:
        return cls._status_map.get((provider_status or "").lower(), "failed")

    @staticmethod
    def _value(response: Dict[str, Any], primary_key: str, fallback_keys: Iterable[str]) -> Any:
        if primary_key in response and response[primary_key] is not None:
            return response[primary_key]
        for key in fallback_keys:
            if key in response and response[key] is not None:
                return response[key]
        return None

    @staticmethod
    def _path(template: str, provider_run_id: str | None = None) -> str:
        return template.format(provider_run_id=provider_run_id)

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
        response = self.transport.post(self._path(self.config.start_run_path), provider_payload)
        run_id = self._value(response, self.config.run_id_key, ("id", "runId"))
        session_id = self._value(response, self.config.session_id_key, ("sessionId", "thread_id"))

        if not run_id:
            raise KeyError("provider start_run response missing run id")

        return AdapterRunStartResult(
            provider="openclaw",
            provider_run_id=run_id,
            provider_session_id=session_id or "",
            status=self.normalize_status(str(self._value(response, self.config.status_key, ("state",)) or "queued")),
            started_at=response.get("started_at") or response.get("startedAt"),
        )

    def send_message(self, provider_run_id: str, content: str, role: str = "system") -> Dict[str, Any]:
        response = self.transport.post(
            self._path(self.config.send_message_path, provider_run_id),
            {"role": role, "content": content},
        )
        return {
            "accepted": bool(response.get("accepted", response.get("ok", True))),
            "queued_at": response.get("queued_at") or response.get("queuedAt"),
        }

    def get_run(self, provider_run_id: str) -> Dict[str, Any]:
        response = self.transport.get(self._path(self.config.get_run_path, provider_run_id))
        run_id = self._value(response, self.config.run_id_key, ("id", "runId")) or provider_run_id
        session_id = self._value(response, self.config.session_id_key, ("sessionId", "thread_id")) or ""
        status = self._value(response, self.config.status_key, ("state",)) or "failed"
        progress = self._value(response, self.config.progress_key, ()) or {}

        return {
            "provider": "openclaw",
            "provider_run_id": run_id,
            "provider_session_id": session_id,
            "status": self.normalize_status(str(status)),
            "progress": progress,
            "updated_at": response.get("updated_at") or response.get("updatedAt"),
        }

    def cancel_run(self, provider_run_id: str) -> Dict[str, Any]:
        response = self.transport.post(self._path(self.config.cancel_run_path, provider_run_id), {})
        status = self._value(response, self.config.status_key, ("state",)) or "canceled"
        return {
            "status": self.normalize_status(str(status)),
            "canceled_at": response.get("canceled_at") or response.get("canceledAt"),
        }

    def stream_events(self, provider_run_id: str) -> List[Dict[str, Any]]:
        response = self.transport.get(self._path(self.config.stream_events_path, provider_run_id))
        events: Iterable[Dict[str, Any]] = response.get(self.config.events_key, response.get("data", []))
        return [self._normalize_event(provider_run_id, event) for event in events]

    def _normalize_event(self, provider_run_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
        provider_type = event.get("type", event.get("event", "run.output"))
        normalized_type = self._map_event_type(provider_type)
        return {
            "event_id": event.get("id") or event.get("event_id"),
            "provider": "openclaw",
            "provider_run_id": provider_run_id,
            "provider_session_id": event.get("session_id") or event.get("sessionId"),
            "type": normalized_type,
            "occurred_at": event.get("occurred_at") or event.get("timestamp"),
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
