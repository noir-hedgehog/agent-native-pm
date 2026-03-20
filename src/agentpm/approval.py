from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List

from .store import AuditEvent, Store, TransitionApproval


class ApprovalService:
    def __init__(self, store: Store) -> None:
        self.store = store

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _to_iso(ts: datetime) -> str:
        return ts.isoformat()

    @staticmethod
    def _parse_iso(iso_ts: str) -> datetime:
        return datetime.fromisoformat(iso_ts)

    def create_transition_approval(self, *, task_id: str, task_session_id: str, from_run_id: str, to_stage_role: str) -> TransitionApproval:
        approval = self.store.create_transition_approval(
            task_session_id=task_session_id,
            from_run_id=from_run_id,
            to_stage_role=to_stage_role,
        )
        self.store.add_audit_event(
            AuditEvent(
                event_type="transition_approval.created",
                task_id=task_id,
                task_session_id=task_session_id,
                payload={"approval_id": approval.approval_id, "to_stage_role": to_stage_role},
                occurred_at=self._to_iso(self._now()),
            )
        )
        return approval

    def approve(self, *, task_id: str, approval_id: str, reviewer_id: str, note: str | None = None) -> TransitionApproval:
        resolved_at = self._to_iso(self._now())
        approval = self.store.update_transition_approval(
            approval_id=approval_id,
            status="approved",
            reviewer_id=reviewer_id,
            decision_note=note,
            resolved_at=resolved_at,
        )
        self.store.add_audit_event(
            AuditEvent(
                event_type="transition_approval.approved",
                task_id=task_id,
                task_session_id=approval.task_session_id,
                payload={"approval_id": approval.approval_id, "reviewer_id": reviewer_id},
                occurred_at=resolved_at,
            )
        )
        return approval

    def reject(self, *, task_id: str, approval_id: str, reviewer_id: str, note: str) -> TransitionApproval:
        resolved_at = self._to_iso(self._now())
        approval = self.store.update_transition_approval(
            approval_id=approval_id,
            status="rejected",
            reviewer_id=reviewer_id,
            decision_note=note,
            resolved_at=resolved_at,
        )
        self.store.add_audit_event(
            AuditEvent(
                event_type="transition_approval.rejected",
                task_id=task_id,
                task_session_id=approval.task_session_id,
                payload={"approval_id": approval.approval_id, "reviewer_id": reviewer_id, "note": note},
                occurred_at=resolved_at,
            )
        )
        return approval

    def evaluate_timeouts(self, *, reminder_after_hours: int = 24, block_after_hours: int = 72) -> Dict[str, List[str]]:
        now = self._now()
        reminders: List[str] = []
        blocked_sessions: List[str] = []

        for approval in self.store.list_pending_transition_approvals():
            created = self._parse_iso(approval.created_at)
            age = now - created

            if age >= timedelta(hours=block_after_hours):
                self.store.update_transition_approval(
                    approval_id=approval.approval_id,
                    status="timed_out",
                    reviewer_id=None,
                    decision_note=f"timed out after {block_after_hours}h",
                    resolved_at=self._to_iso(now),
                )
                self.store.update_task_session_status(approval.task_session_id, "blocked")
                blocked_sessions.append(approval.task_session_id)
            elif age >= timedelta(hours=reminder_after_hours):
                reminders.append(approval.approval_id)

        return {"reminders": reminders, "blocked_sessions": blocked_sessions}
