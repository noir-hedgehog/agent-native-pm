from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .store import AuditEvent, Store


class ReliabilityExecutor:
    """Execute one stage with retry and fallback profile strategy."""

    def __init__(self, store: Store, agent_adapter, plane_adapter) -> None:
        self.store = store
        self.agent_adapter = agent_adapter
        self.plane_adapter = plane_adapter

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _run_once(
        self,
        *,
        task_id: str,
        task_session_id: str,
        stage_role: str,
        agent_profile: str,
        retry_index: int,
        instruction: str,
        context: Dict[str, Any],
    ) -> tuple[bool, str, Optional[str]]:
        run = self.store.create_agent_run(
            task_session_id=task_session_id,
            stage_role=stage_role,
            agent_provider="openclaw",
            agent_profile=agent_profile,
            status="queued",
            retry_index=retry_index,
        )
        self.store.transition_agent_run(run.agent_run_id, "running")
        start = self.agent_adapter.start_run(
            {
                "task_session_id": task_session_id,
                "agent_run_id": run.agent_run_id,
                "task_id": task_id,
                "stage_role": stage_role,
                "instruction": instruction,
                "context": context,
                "policy": {"max_retry": 1},
            }
        )
        provider_run_id = getattr(start, "provider_run_id", None)
        if provider_run_id is None:
            provider_run_id = start.get("provider_run_id")

        failure_reason = None
        succeeded = False
        for event in self.agent_adapter.stream_events(provider_run_id):
            event_type = event.get("type")
            payload = event.get("payload", {})
            if event_type == "run.completed":
                self.store.transition_agent_run(run.agent_run_id, "succeeded")
                self.store.add_audit_event(
                    AuditEvent(
                        event_type="agent_run.completed",
                        task_id=task_id,
                        task_session_id=task_session_id,
                        payload={"agent_run_id": run.agent_run_id, "agent_profile": agent_profile},
                        occurred_at=self._now_iso(),
                    )
                )
                succeeded = True
                break
            if event_type == "run.failed":
                failure_reason = payload.get("error", "run failed")
                break

        if not succeeded:
            self.store.transition_agent_run(run.agent_run_id, "failed")
            self.store.add_audit_event(
                AuditEvent(
                    event_type="agent_run.failed",
                    task_id=task_id,
                    task_session_id=task_session_id,
                    payload={
                        "agent_run_id": run.agent_run_id,
                        "agent_profile": agent_profile,
                        "reason": failure_reason or "run failed",
                    },
                    occurred_at=self._now_iso(),
                )
            )
            return False, run.agent_run_id, failure_reason or "run failed"

        return True, run.agent_run_id, None

    def execute_with_retry_and_fallback(
        self,
        *,
        task_id: str,
        task_session_id: str,
        stage_role: str,
        primary_profile: str,
        backup_profile: str | None,
        instruction: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        attempts = [
            (primary_profile, 0),
            (primary_profile, 1),
        ]
        if backup_profile:
            attempts.append((backup_profile, 0))

        last_failure = "unknown failure"
        last_run_id = None

        for profile, retry_index in attempts:
            ok, run_id, failure_reason = self._run_once(
                task_id=task_id,
                task_session_id=task_session_id,
                stage_role=stage_role,
                agent_profile=profile,
                retry_index=retry_index,
                instruction=instruction,
                context=context,
            )
            if ok:
                return {
                    "completed": True,
                    "agent_run_id": run_id,
                    "profile": profile,
                    "used_fallback": profile != primary_profile,
                }
            last_failure = failure_reason or last_failure
            last_run_id = run_id

        self.store.update_task_session_status(task_session_id, "blocked")
        self.plane_adapter.post_stage_failed(
            task_id=task_id,
            stage_role=stage_role,
            reason=last_failure,
            retries_used=2 if backup_profile else 1,
            escalation_request="manual intervention required",
            task_session_id=task_session_id,
            agent_run_id=last_run_id,
        )
        self.plane_adapter.update_task_status(task_id=task_id, status="blocked")

        return {
            "completed": False,
            "agent_run_id": last_run_id,
            "profile": None,
            "used_fallback": bool(backup_profile),
            "reason": last_failure,
        }
