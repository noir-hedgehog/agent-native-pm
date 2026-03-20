import unittest

from agentpm.reporting import ReportingService
from agentpm.store import AuditEvent, InMemoryStore


class ReportingServiceTests(unittest.TestCase):
    def test_metrics_and_timeline(self):
        store = InMemoryStore()
        session, _ = store.get_or_create_session("evt:task", "proj_1", "task_1")

        store.add_audit_event(
            AuditEvent(
                event_type="agent_run.created",
                task_id="task_1",
                task_session_id=session.task_session_id,
                payload={"agent_run_id": "ar_1"},
                occurred_at="2026-03-20T00:00:00+00:00",
            )
        )
        store.add_audit_event(
            AuditEvent(
                event_type="agent_run.completed",
                task_id="task_1",
                task_session_id=session.task_session_id,
                payload={"agent_run_id": "ar_1"},
                occurred_at="2026-03-20T00:00:10+00:00",
            )
        )
        store.add_audit_event(
            AuditEvent(
                event_type="transition_approval.approved",
                task_id="task_1",
                task_session_id=session.task_session_id,
                payload={"approval_id": "ap_1"},
                occurred_at="2026-03-20T00:00:20+00:00",
            )
        )
        store.add_audit_event(
            AuditEvent(
                event_type="stage.rejected",
                task_id="task_1",
                task_session_id=session.task_session_id,
                payload={"reason": "needs fix"},
                occurred_at="2026-03-20T00:00:30+00:00",
            )
        )

        service = ReportingService(store)
        metrics = service.get_project_metrics("proj_1")

        self.assertEqual(metrics["task_count"], 1)
        self.assertEqual(metrics["first_pass_approval_rate"], 1.0)
        self.assertEqual(metrics["mean_transition_lead_time_seconds"], 10.0)
        self.assertEqual(metrics["human_interventions_per_task"], 2.0)
        self.assertEqual(metrics["rejection_rate"], 1.0)

        timeline = service.get_task_timeline("task_1")
        self.assertEqual(len(timeline["events"]), 4)
        self.assertEqual(timeline["events"][0]["event_type"], "agent_run.created")


if __name__ == "__main__":
    unittest.main()
