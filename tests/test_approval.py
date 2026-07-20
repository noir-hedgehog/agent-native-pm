import unittest
from datetime import datetime, timedelta, timezone

from agentpm.approval import ApprovalService
from agentpm.store import InMemoryStore


class ApprovalServiceTests(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryStore()
        self.service = ApprovalService(self.store)
        self.session, _ = self.store.get_or_create_session("evt:task", "proj_1", "task_1")
        self.run = self.store.create_agent_run(
            task_session_id=self.session.task_session_id,
            stage_role="tester",
            agent_provider="openclaw",
            agent_profile="openclaw-tester-v1",
        )

    def test_create_and_approve_transition(self):
        approval = self.service.create_transition_approval(
            task_id="task_1",
            task_session_id=self.session.task_session_id,
            from_run_id=self.run.agent_run_id,
            to_stage_role="reviewer",
        )
        approved = self.service.approve(task_id="task_1", approval_id=approval.approval_id, reviewer_id="user_1")

        self.assertEqual(approved.status, "approved")
        events = self.store.list_audit_events()
        event_types = [e.event_type for e in events]
        self.assertIn("transition_approval.created", event_types)
        self.assertIn("transition_approval.approved", event_types)

    def test_timeout_evaluation_reminds_and_blocks(self):
        approval = self.service.create_transition_approval(
            task_id="task_1",
            task_session_id=self.session.task_session_id,
            from_run_id=self.run.agent_run_id,
            to_stage_role="reviewer",
        )

        pending = self.store._approvals_by_id[approval.approval_id]
        old_created = (datetime.now(timezone.utc) - timedelta(hours=80)).isoformat()
        self.store._approvals_by_id[approval.approval_id] = pending.__class__(
            approval_id=pending.approval_id,
            task_session_id=pending.task_session_id,
            from_run_id=pending.from_run_id,
            to_stage_role=pending.to_stage_role,
            status=pending.status,
            reviewer_id=pending.reviewer_id,
            decision_note=pending.decision_note,
            created_at=old_created,
            resolved_at=pending.resolved_at,
        )

        result = self.service.evaluate_timeouts(reminder_after_hours=24, block_after_hours=72)

        self.assertEqual(result["reminders"], [])
        self.assertEqual(result["blocked_sessions"], [self.session.task_session_id])
        session = self.store.get_task_session(self.session.task_session_id)
        self.assertEqual(session.status, "blocked")

    def test_reminder_is_audited_once(self):
        approval = self.service.create_transition_approval(
            task_id="task_1",
            task_session_id=self.session.task_session_id,
            from_run_id=self.run.agent_run_id,
            to_stage_role="reviewer",
        )
        pending = self.store._approvals_by_id[approval.approval_id]
        self.store._approvals_by_id[approval.approval_id] = pending.__class__(
            **{**pending.__dict__, "created_at": (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()}
        )

        first = self.service.evaluate_timeouts(reminder_after_hours=24, block_after_hours=72)
        second = self.service.evaluate_timeouts(reminder_after_hours=24, block_after_hours=72)

        self.assertEqual(first["reminders"], [approval.approval_id])
        self.assertEqual(second["reminders"], [])
        reminders = [event for event in self.store.list_audit_events() if event.event_type == "transition_approval.reminder"]
        self.assertEqual(len(reminders), 1)


if __name__ == "__main__":
    unittest.main()
