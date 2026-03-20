from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from .store import AuditEvent, Store


class RejectionService:
    def __init__(self, store: Store) -> None:
        self.store = store

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def reject_to_previous_stage(
        self,
        *,
        task_id: str,
        task_session_id: str,
        current_stage_role: str,
        pipeline_roles: List[str],
        reviewer_id: str,
        reason: str,
    ):
        if current_stage_role not in pipeline_roles:
            raise ValueError(f"unknown current stage role: {current_stage_role}")

        current_index = pipeline_roles.index(current_stage_role)
        if current_index == 0:
            raise ValueError("cannot reject the first stage")

        previous_role = pipeline_roles[current_index - 1]
        all_runs = self.store.list_agent_runs_for_session(task_session_id)
        previous_runs = [run for run in all_runs if run.stage_role == previous_role]
        if not previous_runs:
            raise ValueError(f"no previous stage runs found for role={previous_role}")

        previous_run = previous_runs[-1]
        rerun = self.store.create_agent_run(
            task_session_id=task_session_id,
            stage_role=previous_run.stage_role,
            agent_provider=previous_run.agent_provider,
            agent_profile=previous_run.agent_profile,
            status="queued",
            retry_index=previous_run.retry_index + 1,
            provider_session_id=None,
        )

        self.store.add_audit_event(
            AuditEvent(
                event_type="stage.rejected",
                task_id=task_id,
                task_session_id=task_session_id,
                payload={
                    "current_stage": current_stage_role,
                    "rejected_to": previous_role,
                    "reason": reason,
                    "reviewer_id": reviewer_id,
                    "previous_run_id": previous_run.agent_run_id,
                    "rerun_id": rerun.agent_run_id,
                },
                occurred_at=self._now_iso(),
            )
        )

        return {
            "rejected_to": previous_role,
            "previous_run_id": previous_run.agent_run_id,
            "rerun_agent_run_id": rerun.agent_run_id,
            "reason": reason,
        }
