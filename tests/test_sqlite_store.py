import tempfile
import unittest

from agentpm.persistence.sqlite_store import SqliteStore
from agentpm.store import AuditEvent


class SqliteStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = f"{self.temp_dir.name}/agentpm.db"
        self.store = SqliteStore(self.db_path)
        self.store.run_migrations()

    def tearDown(self) -> None:
        self.store.close()
        self.temp_dir.cleanup()

    def test_migrations_create_expected_tables(self) -> None:
        rows = self.store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        table_names = {row["name"] for row in rows}

        self.assertTrue({
            "project_policy",
            "task_session",
            "idempotency_key",
            "agent_run",
            "handoff_contract",
            "transition_approval",
            "audit_event",
        }.issubset(table_names))

    def test_get_or_create_session_is_idempotent(self) -> None:
        first, first_dup = self.store.get_or_create_session("evt:task", "proj_1", "task_1")
        second, second_dup = self.store.get_or_create_session("evt:task", "proj_1", "task_1")

        self.assertFalse(first_dup)
        self.assertTrue(second_dup)
        self.assertEqual(first.task_session_id, second.task_session_id)

    def test_task_session_status_update(self) -> None:
        session, _ = self.store.get_or_create_session("evt:task-2", "proj_1", "task_2")
        updated = self.store.update_task_session_status(session.task_session_id, "awaiting_review")

        self.assertEqual(updated.status, "awaiting_review")

    def test_agent_run_lifecycle_and_transition_guards(self) -> None:
        session, _ = self.store.get_or_create_session("evt:task-3", "proj_1", "task_3")
        run = self.store.create_agent_run(
            task_session_id=session.task_session_id,
            stage_role="coder",
            agent_provider="openclaw",
            agent_profile="openclaw-coder-v1",
        )

        running = self.store.transition_agent_run(run.agent_run_id, "running")
        succeeded = self.store.transition_agent_run(run.agent_run_id, "succeeded")

        self.assertEqual(running.status, "running")
        self.assertEqual(succeeded.status, "succeeded")

        with self.assertRaises(ValueError):
            self.store.transition_agent_run(run.agent_run_id, "running")

    def test_audit_event_write_and_read(self) -> None:
        session, _ = self.store.get_or_create_session("evt:task-4", "proj_1", "task_4")
        self.store.add_audit_event(
            AuditEvent(
                event_type="webhook.assignment.accepted",
                task_id="task_4",
                task_session_id=session.task_session_id,
                payload={"duplicate": False},
                occurred_at="2026-03-20T00:00:00+00:00",
            )
        )

        events = self.store.list_audit_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "webhook.assignment.accepted")
        self.assertFalse(events[0].payload["duplicate"])

    def test_handoff_contract_write_and_read(self) -> None:
        session, _ = self.store.get_or_create_session("evt:task-5", "proj_1", "task_5")
        run = self.store.create_agent_run(
            task_session_id=session.task_session_id,
            stage_role="coder",
            agent_provider="openclaw",
            agent_profile="openclaw-coder-v1",
        )
        self.store.save_handoff_contract(
            agent_run_id=run.agent_run_id,
            goal="fix login timeout",
            completed=["patched retry logic"],
            evidence=["tests:pass"],
            risks=["needs load test"],
            next_actions=["tester validates mobile"],
            confidence="medium",
        )
        contract = self.store.get_handoff_contract(run.agent_run_id)

        self.assertIsNotNone(contract)
        self.assertEqual(contract.goal, "fix login timeout")
        self.assertEqual(contract.completed, ["patched retry logic"])

    def test_transition_approval_crud(self) -> None:
        session, _ = self.store.get_or_create_session("evt:task-6", "proj_1", "task_6")
        run = self.store.create_agent_run(
            task_session_id=session.task_session_id,
            stage_role="tester",
            agent_provider="openclaw",
            agent_profile="openclaw-tester-v1",
        )
        approval = self.store.create_transition_approval(
            task_session_id=session.task_session_id,
            from_run_id=run.agent_run_id,
            to_stage_role="reviewer",
        )
        pending = self.store.list_pending_transition_approvals()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].approval_id, approval.approval_id)

        approved = self.store.update_transition_approval(
            approval_id=approval.approval_id,
            status="approved",
            reviewer_id="user_1",
            decision_note="looks good",
            resolved_at="2026-03-20T01:00:00+00:00",
        )
        self.assertEqual(approved.status, "approved")
        self.assertEqual(self.store.list_pending_transition_approvals(), [])


if __name__ == "__main__":
    unittest.main()
