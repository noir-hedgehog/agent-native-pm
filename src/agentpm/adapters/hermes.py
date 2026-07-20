from __future__ import annotations

import os
from dataclasses import dataclass

from .openclaw import AdapterRunStartResult, OpenClawAdapter, OpenClawAdapterConfig, OpenClawTransport


@dataclass
class HermesAdapterConfig(OpenClawAdapterConfig):
    """Hermes HTTP mapping.

    Hermes is intentionally treated as the same provider-agnostic run contract as
    OpenClaw: start a run, poll run state, cancel, and read normalized events.
    The HERMES_* environment variables let deployments map onto their concrete
    Hermes API without changing orchestrator code.
    """

    @classmethod
    def from_env(cls) -> "HermesAdapterConfig":
        return cls(
            start_run_path=os.environ.get("HERMES_START_RUN_PATH", "/runs"),
            send_message_path=os.environ.get("HERMES_SEND_MESSAGE_PATH", "/runs/{provider_run_id}/messages"),
            get_run_path=os.environ.get("HERMES_GET_RUN_PATH", "/runs/{provider_run_id}"),
            cancel_run_path=os.environ.get("HERMES_CANCEL_RUN_PATH", "/runs/{provider_run_id}/cancel"),
            stream_events_path=os.environ.get("HERMES_STREAM_EVENTS_PATH", "/runs/{provider_run_id}/events"),
            run_id_key=os.environ.get("HERMES_RUN_ID_KEY", "run_id"),
            session_id_key=os.environ.get("HERMES_SESSION_ID_KEY", "session_id"),
            status_key=os.environ.get("HERMES_STATUS_KEY", "status"),
            progress_key=os.environ.get("HERMES_PROGRESS_KEY", "progress"),
            events_key=os.environ.get("HERMES_EVENTS_KEY", "events"),
        )


class HermesAdapter(OpenClawAdapter):
    """Hermes connector implementing the normalized agent adapter contract."""

    provider_name = "hermes"

    def __init__(self, transport: OpenClawTransport, config: HermesAdapterConfig | None = None) -> None:
        super().__init__(transport=transport, config=config or HermesAdapterConfig())

    def start_run(self, payload):
        result = super().start_run(payload)
        return AdapterRunStartResult(
            provider=self.provider_name,
            provider_run_id=result.provider_run_id,
            provider_session_id=result.provider_session_id,
            status=result.status,
            started_at=result.started_at,
        )

    def get_run(self, provider_run_id: str):
        result = super().get_run(provider_run_id)
        result["provider"] = self.provider_name
        return result

    def stream_events(self, provider_run_id: str):
        events = super().stream_events(provider_run_id)
        for event in events:
            event["provider"] = self.provider_name
        return events
