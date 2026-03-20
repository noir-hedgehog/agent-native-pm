from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Protocol

from .store import AuditEvent, Store
from .webhook import handle_assignment_webhook, normalize_assignment_event


class AgentAdapter(Protocol):
    def start_run(self, payload: Dict[str, Any]) -> Any:
        ...

    def stream_events(self, provider_run_id: str) -> list[Dict[str, Any]]:
        ...


class PlaneAdapter(Protocol):
    def post_stage_started(self, **kwargs) -> Dict[str, Any]:
        ...

    def post_stage_progress(self, **kwargs) -> Dict[str, Any]:
        ...

    def post_stage_completed(self, **kwargs) -> Dict[str, Any]:
        ...

    def post_stage_failed(self, **kwargs) -> Dict[str, Any]:
        ...

    def update_task_status(self, *, task_id: str, status: str) -> Dict[str, Any]:
        ...


class AssignmentOrchestrator:
    def __init__(self, store: Store, agent_adapter: AgentAdapter, plane_adapter: PlaneAdapter, secret: str) -> None:
        self.store = store
        self.agent_adapter = agent_adapter
        self.plane_adapter = plane_adapter
        self.secret = secret

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def process_assignment(self, *, raw_body: bytes, headers: Mapping[str, str]) -> Dict[str, Any]:
        status, response = handle_assignment_webhook(
            raw_body=raw_body,
            headers=headers,
            secret=self.secret,
            store=self.store,
        )
        if status != 202:
            raise RuntimeError(f"unexpected webhook handler status: {status}")

        if response["duplicate"]:
            return {
                "accepted": True,
                "duplicate": True,
                "task_session_id": response["task_session_id"],
                "agent_run_id": None,
            }

        payload = json.loads(raw_body.decode("utf-8"))
        event = normalize_assignment_event(payload)
        task = payload.get("task", {})
        assignee_id = event.get("assignee_id") or "agent_openclaw_default"

        run = self.store.create_agent_run(
            task_session_id=response["task_session_id"],
            stage_role="coder",
            agent_provider="openclaw",
            agent_profile=assignee_id,
            status="queued",
        )

        self.store.add_audit_event(
            AuditEvent(
                event_type="agent_run.created",
                task_id=event["task_id"],
                task_session_id=response["task_session_id"],
                payload={"agent_run_id": run.agent_run_id, "agent_profile": assignee_id},
                occurred_at=self._now_iso(),
            )
        )

        self.plane_adapter.post_stage_started(
            task_id=event["task_id"],
            stage_role="coder",
            agent_profile=assignee_id,
            started_at=self._now_iso(),
            task_session_id=response["task_session_id"],
            agent_run_id=run.agent_run_id,
        )

        start_result = self.agent_adapter.start_run(
            {
                "task_session_id": response["task_session_id"],
                "agent_run_id": run.agent_run_id,
                "task_id": event["task_id"],
                "stage_role": "coder",
                "instruction": task.get("description") or task.get("title") or "Complete assigned task",
                "context": {
                    "task_title": task.get("title"),
                    "task_description": task.get("description"),
                    "task_key": task.get("key"),
                },
                "policy": {"max_retry": 1},
            }
        )

        self.store.transition_agent_run(run.agent_run_id, "running")
        self.store.add_audit_event(
            AuditEvent(
                event_type="agent_run.started",
                task_id=event["task_id"],
                task_session_id=response["task_session_id"],
                payload={
                    "agent_run_id": run.agent_run_id,
                    "provider_run_id": start_result.provider_run_id,
                    "provider_session_id": start_result.provider_session_id,
                },
                occurred_at=self._now_iso(),
            )
        )

        events = self.agent_adapter.stream_events(start_result.provider_run_id)
        completed = False

        for stream_event in events:
            stream_type = stream_event.get("type")
            payload_data = stream_event.get("payload", {})

            if stream_type in {"run.output", "run.progress"}:
                summary = payload_data.get("content") or payload_data.get("summary") or "in progress"
                self.plane_adapter.post_stage_progress(
                    task_id=event["task_id"],
                    stage_role="coder",
                    summary=summary,
                    evidence=None,
                    task_session_id=response["task_session_id"],
                    agent_run_id=run.agent_run_id,
                )

            if stream_type == "run.completed":
                handoff = payload_data.get("handoff_hint", {})
                handoff_goal = handoff.get("goal") or "complete assigned coding task"
                handoff_completed = handoff.get("completed") or []
                handoff_evidence = handoff.get("evidence") or []
                handoff_risks = handoff.get("risks") or []
                handoff_next = handoff.get("next_actions") or []
                handoff_confidence = handoff.get("confidence") or "medium"

                self.store.save_handoff_contract(
                    agent_run_id=run.agent_run_id,
                    goal=handoff_goal,
                    completed=handoff_completed,
                    evidence=handoff_evidence,
                    risks=handoff_risks,
                    next_actions=handoff_next,
                    confidence=handoff_confidence,
                )
                self.store.transition_agent_run(run.agent_run_id, "succeeded")
                self.store.update_task_session_status(response["task_session_id"], "awaiting_review")
                self.plane_adapter.post_stage_completed(
                    task_id=event["task_id"],
                    handoff={
                        "goal": handoff_goal,
                        "completed": handoff_completed,
                        "evidence": handoff_evidence,
                        "risks": handoff_risks,
                        "next_actions": handoff_next,
                        "confidence": handoff_confidence,
                    },
                    task_session_id=response["task_session_id"],
                    agent_run_id=run.agent_run_id,
                )
                self.plane_adapter.update_task_status(task_id=event["task_id"], status="awaiting_review")
                self.store.add_audit_event(
                    AuditEvent(
                        event_type="agent_run.completed",
                        task_id=event["task_id"],
                        task_session_id=response["task_session_id"],
                        payload={"agent_run_id": run.agent_run_id},
                        occurred_at=self._now_iso(),
                    )
                )
                completed = True

            if stream_type == "run.failed":
                reason = payload_data.get("error", "agent run failed")
                self.store.transition_agent_run(run.agent_run_id, "failed")
                self.store.update_task_session_status(response["task_session_id"], "failed")
                self.plane_adapter.post_stage_failed(
                    task_id=event["task_id"],
                    stage_role="coder",
                    reason=reason,
                    retries_used=0,
                    escalation_request="manual intervention required",
                    task_session_id=response["task_session_id"],
                    agent_run_id=run.agent_run_id,
                )
                self.plane_adapter.update_task_status(task_id=event["task_id"], status="failed")
                self.store.add_audit_event(
                    AuditEvent(
                        event_type="agent_run.failed",
                        task_id=event["task_id"],
                        task_session_id=response["task_session_id"],
                        payload={"agent_run_id": run.agent_run_id, "reason": reason},
                        occurred_at=self._now_iso(),
                    )
                )

        return {
            "accepted": True,
            "duplicate": False,
            "task_session_id": response["task_session_id"],
            "agent_run_id": run.agent_run_id,
            "completed": completed,
        }
