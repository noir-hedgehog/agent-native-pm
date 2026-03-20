import unittest

from agentpm.rejection import RejectionService
from agentpm.store import InMemoryStore


class RejectionServiceTests(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryStore()
        self.service = RejectionService(self.store)
        self.session, _ = self.store.get_or_create_session("evt:task", "proj_1", "task_1")

    def test_rejects_only_to_immediate_previous_stage(self):
        coder = self.store.create_agent_run(
            task_session_id=self.session.task_session_id,
            stage_role="coder",
            agent_provider="openclaw",
            agent_profile="openclaw-coder-v1",
            status="queued",
        )
        self.store.transition_agent_run(coder.agent_run_id, "running")
        self.store.transition_agent_run(coder.agent_run_id, "succeeded")

        tester = self.store.create_agent_run(
            task_session_id=self.session.task_session_id,
            stage_role="tester",
            agent_provider="openclaw",
            agent_profile="openclaw-tester-v1",
            status="queued",
        )
        self.store.transition_agent_run(tester.agent_run_id, "running")

        result = self.service.reject_to_previous_stage(
            task_id="task_1",
            task_session_id=self.session.task_session_id,
            current_stage_role="tester",
            pipeline_roles=["coder", "tester", "reviewer"],
            reviewer_id="user_1",
            reason="missing edge case coverage",
        )

        self.assertEqual(result["rejected_to"], "coder")
        rerun = self.store.get_agent_run(result["rerun_agent_run_id"])
        self.assertEqual(rerun.stage_role, "coder")
        self.assertEqual(rerun.retry_index, 1)

        event_types = [e.event_type for e in self.store.list_audit_events()]
        self.assertIn("stage.rejected", event_types)

    def test_rejecting_first_stage_raises(self):
        with self.assertRaises(ValueError):
            self.service.reject_to_previous_stage(
                task_id="task_1",
                task_session_id=self.session.task_session_id,
                current_stage_role="coder",
                pipeline_roles=["coder", "tester", "reviewer"],
                reviewer_id="user_1",
                reason="invalid",
            )


if __name__ == "__main__":
    unittest.main()
