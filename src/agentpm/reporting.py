from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from .store import Store


class ReportingService:
    def __init__(self, store: Store) -> None:
        self.store = store

    @staticmethod
    def _parse_iso(ts: str) -> datetime:
        return datetime.fromisoformat(ts)

    def get_project_metrics(self, project_id: str) -> Dict[str, float | int]:
        sessions = [session for session in self.store.list_task_sessions() if session.project_id == project_id]
        if not sessions:
            return {
                "first_pass_approval_rate": 0.0,
                "mean_transition_lead_time_seconds": 0.0,
                "human_interventions_per_task": 0.0,
                "rejection_rate": 0.0,
                "task_count": 0,
            }

        session_ids = {session.task_session_id for session in sessions}
        all_events = [event for event in self.store.list_audit_events() if event.task_session_id in session_ids]

        approvals_approved = sum(1 for e in all_events if e.event_type == "transition_approval.approved")
        approvals_rejected = sum(1 for e in all_events if e.event_type == "transition_approval.rejected")
        approval_total = approvals_approved + approvals_rejected
        first_pass_rate = approvals_approved / approval_total if approval_total else 0.0

        created_by_run: Dict[str, datetime] = {}
        lead_times: List[float] = []
        for event in all_events:
            run_id = event.payload.get("agent_run_id") if isinstance(event.payload, dict) else None
            if not run_id:
                continue
            if event.event_type == "agent_run.created":
                created_by_run[run_id] = self._parse_iso(event.occurred_at)
            if event.event_type == "agent_run.completed" and run_id in created_by_run:
                lead_times.append((self._parse_iso(event.occurred_at) - created_by_run[run_id]).total_seconds())

        mean_lead_time = sum(lead_times) / len(lead_times) if lead_times else 0.0

        human_events = {
            "transition_approval.approved",
            "transition_approval.rejected",
            "stage.rejected",
        }
        interventions = sum(1 for e in all_events if e.event_type in human_events)
        interventions_per_task = interventions / len(sessions)

        stage_rejections = sum(1 for e in all_events if e.event_type == "stage.rejected")
        completed_handoffs = sum(1 for e in all_events if e.event_type == "agent_run.completed")
        rejection_rate = stage_rejections / completed_handoffs if completed_handoffs else 0.0

        return {
            "first_pass_approval_rate": round(first_pass_rate, 4),
            "mean_transition_lead_time_seconds": round(mean_lead_time, 2),
            "human_interventions_per_task": round(interventions_per_task, 4),
            "rejection_rate": round(rejection_rate, 4),
            "task_count": len(sessions),
        }

    def get_task_timeline(self, task_id: str) -> Dict[str, object]:
        events = sorted(self.store.list_audit_events_for_task(task_id), key=lambda e: e.occurred_at)
        return {
            "task_id": task_id,
            "events": [
                {
                    "event_type": event.event_type,
                    "task_session_id": event.task_session_id,
                    "payload": event.payload,
                    "occurred_at": event.occurred_at,
                }
                for event in events
            ],
        }
