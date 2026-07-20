from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class DevRunStartResult:
    provider: str
    provider_run_id: str
    provider_session_id: str
    status: str


class DevAgentAdapter:
    """Deterministic local agent adapter for smoke tests and offline demos."""

    def start_run(self, payload: Dict[str, Any]) -> DevRunStartResult:
        agent_run_id = payload["agent_run_id"]
        return DevRunStartResult(
            provider="dev",
            provider_run_id=f"dev_run_{agent_run_id}",
            provider_session_id=f"dev_session_{agent_run_id}",
            status="queued",
        )

    def stream_events(self, provider_run_id: str) -> List[Dict[str, Any]]:
        return [
            {
                "type": "run.progress",
                "payload": {"summary": "dev agent accepted the assignment"},
            },
            {
                "type": "run.completed",
                "payload": {
                    "handoff_hint": {
                        "goal": "complete the assigned task in dev mode",
                        "completed": ["created a deterministic MVP completion event"],
                        "evidence": [provider_run_id],
                        "risks": ["replace dev adapter with OpenClaw or Hermes for production use"],
                        "next_actions": ["review Plane write-back and connect a real agent provider"],
                        "confidence": "medium",
                    }
                },
            },
        ]


class DevPlaneWritebackAdapter:
    """No-op Plane adapter that keeps local orchestration runnable without Plane credentials."""

    def __init__(self) -> None:
        self.comments: list[Dict[str, Any]] = []
        self.status_updates: list[Dict[str, str]] = []

    def post_stage_started(self, **kwargs) -> Dict[str, Any]:
        self.comments.append({"type": "stage_started", **kwargs})
        return {"ok": True, "mode": "dev"}

    def post_stage_progress(self, **kwargs) -> Dict[str, Any]:
        self.comments.append({"type": "stage_progress", **kwargs})
        return {"ok": True, "mode": "dev"}

    def post_stage_completed(self, **kwargs) -> Dict[str, Any]:
        self.comments.append({"type": "stage_completed", **kwargs})
        return {"ok": True, "mode": "dev"}

    def post_stage_failed(self, **kwargs) -> Dict[str, Any]:
        self.comments.append({"type": "stage_failed", **kwargs})
        return {"ok": True, "mode": "dev"}

    def update_task_status(self, *, task_id: str, status: str, **kwargs) -> Dict[str, Any]:
        self.status_updates.append({"task_id": task_id, "status": status, **kwargs})
        return {"ok": True, "mode": "dev"}
