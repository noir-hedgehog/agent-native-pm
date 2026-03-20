from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from .store import AuditEvent, Store


class SerialPipelineExecutor:
    """Executes deterministic stage order for a task session."""

    def __init__(self, store: Store, agent_adapter, plane_adapter) -> None:
        self.store = store
        self.agent_adapter = agent_adapter
        self.plane_adapter = plane_adapter

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _normalize_handoff(payload: Dict[str, Any]) -> Dict[str, Any]:
        handoff = payload.get("handoff_hint", {})
        return {
            "goal": handoff.get("goal") or "complete stage",
            "completed": handoff.get("completed") or [],
            "evidence": handoff.get("evidence") or [],
            "risks": handoff.get("risks") or [],
            "next_actions": handoff.get("next_actions") or [],
            "confidence": handoff.get("confidence") or "medium",
        }

    def execute(
        self,
        *,
        task_session_id: str,
        task_id: str,
        task: Dict[str, Any],
        pipeline_roles: List[str],
        agent_profile_by_role: Dict[str, str],
    ) -> Dict[str, Any]:
        previous_handoff: Dict[str, Any] | None = None
        created_runs: List[str] = []

        for role in pipeline_roles:
            agent_profile = agent_profile_by_role[role]
            run = self.store.create_agent_run(
                task_session_id=task_session_id,
                stage_role=role,
                agent_provider="openclaw",
                agent_profile=agent_profile,
                status="queued",
            )
            created_runs.append(run.agent_run_id)

            self.store.add_audit_event(
                AuditEvent(
                    event_type="agent_run.created",
                    task_id=task_id,
                    task_session_id=task_session_id,
                    payload={"agent_run_id": run.agent_run_id, "stage_role": role},
                    occurred_at=self._now_iso(),
                )
            )

            self.plane_adapter.post_stage_started(
                task_id=task_id,
                stage_role=role,
                agent_profile=agent_profile,
                started_at=self._now_iso(),
                task_session_id=task_session_id,
                agent_run_id=run.agent_run_id,
            )

            start_result = self.agent_adapter.start_run(
                {
                    "task_session_id": task_session_id,
                    "agent_run_id": run.agent_run_id,
                    "task_id": task_id,
                    "stage_role": role,
                    "instruction": f"Execute stage: {role}",
                    "context": {
                        "task_title": task.get("title"),
                        "task_description": task.get("description"),
                        "task_key": task.get("key"),
                        "previous_handoff": previous_handoff,
                    },
                    "policy": {"max_retry": 1},
                }
            )

            self.store.transition_agent_run(run.agent_run_id, "running")
            self.store.add_audit_event(
                AuditEvent(
                    event_type="agent_run.started",
                    task_id=task_id,
                    task_session_id=task_session_id,
                    payload={
                        "agent_run_id": run.agent_run_id,
                        "provider_run_id": start_result.provider_run_id,
                    },
                    occurred_at=self._now_iso(),
                )
            )

            completed = False
            for stream_event in self.agent_adapter.stream_events(start_result.provider_run_id):
                stream_type = stream_event.get("type")
                payload_data = stream_event.get("payload", {})

                if stream_type in {"run.output", "run.progress"}:
                    summary = payload_data.get("summary") or payload_data.get("content") or "in progress"
                    self.plane_adapter.post_stage_progress(
                        task_id=task_id,
                        stage_role=role,
                        summary=summary,
                        evidence=None,
                        task_session_id=task_session_id,
                        agent_run_id=run.agent_run_id,
                    )

                if stream_type == "run.failed":
                    reason = payload_data.get("error", "agent run failed")
                    self.store.transition_agent_run(run.agent_run_id, "failed")
                    self.store.update_task_session_status(task_session_id, "failed")
                    self.plane_adapter.post_stage_failed(
                        task_id=task_id,
                        stage_role=role,
                        reason=reason,
                        retries_used=0,
                        escalation_request="manual intervention required",
                        task_session_id=task_session_id,
                        agent_run_id=run.agent_run_id,
                    )
                    self.plane_adapter.update_task_status(task_id=task_id, status="failed")
                    return {
                        "completed": False,
                        "failed_stage": role,
                        "task_session_id": task_session_id,
                        "agent_run_ids": created_runs,
                    }

                if stream_type == "run.completed":
                    handoff = self._normalize_handoff(payload_data)
                    previous_handoff = handoff
                    self.store.save_handoff_contract(
                        agent_run_id=run.agent_run_id,
                        goal=handoff["goal"],
                        completed=handoff["completed"],
                        evidence=handoff["evidence"],
                        risks=handoff["risks"],
                        next_actions=handoff["next_actions"],
                        confidence=handoff["confidence"],
                    )
                    self.store.transition_agent_run(run.agent_run_id, "succeeded")
                    self.plane_adapter.post_stage_completed(
                        task_id=task_id,
                        handoff=handoff,
                        task_session_id=task_session_id,
                        agent_run_id=run.agent_run_id,
                    )
                    self.store.add_audit_event(
                        AuditEvent(
                            event_type="agent_run.completed",
                            task_id=task_id,
                            task_session_id=task_session_id,
                            payload={"agent_run_id": run.agent_run_id, "stage_role": role},
                            occurred_at=self._now_iso(),
                        )
                    )
                    completed = True

            if not completed:
                self.store.transition_agent_run(run.agent_run_id, "failed")
                self.store.update_task_session_status(task_session_id, "failed")
                self.plane_adapter.update_task_status(task_id=task_id, status="failed")
                return {
                    "completed": False,
                    "failed_stage": role,
                    "task_session_id": task_session_id,
                    "agent_run_ids": created_runs,
                }

        self.store.update_task_session_status(task_session_id, "awaiting_review")
        self.plane_adapter.update_task_status(task_id=task_id, status="awaiting_review")
        self.plane_adapter.post_stage_progress(
            task_id=task_id,
            stage_role="pipeline",
            summary="Pipeline completed all stages",
            evidence=None,
            task_session_id=task_session_id,
            agent_run_id=None,
        )

        return {
            "completed": True,
            "task_session_id": task_session_id,
            "agent_run_ids": created_runs,
            "final_handoff": previous_handoff,
        }
