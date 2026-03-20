import unittest

from agentpm.adapters.plane import PlaneWritebackAdapter


class FlakyFakePlaneTransport:
    def __init__(self):
        self.comments = []
        self.status_updates = []
        self.fail_first_comment = True

    def post_comment(self, task_id, body):
        if self.fail_first_comment:
            self.fail_first_comment = False
            raise RuntimeError("temporary failure")
        self.comments.append((task_id, body))
        return {"ok": True, "task_id": task_id, "body": body}

    def patch_task(self, task_id, payload):
        self.status_updates.append((task_id, payload))
        return {"ok": True, "task_id": task_id, **payload}


class PlaneWritebackAdapterTests(unittest.TestCase):
    def setUp(self):
        self.transport = FlakyFakePlaneTransport()
        self.adapter = PlaneWritebackAdapter(self.transport, max_attempts=2, retry_delay_seconds=0)

    def test_retries_comment_post_then_succeeds(self):
        result = self.adapter.post_stage_started(
            task_id="task_1",
            stage_role="coder",
            agent_profile="openclaw-coder-v1",
            started_at="2026-03-20T01:00:00Z",
            task_session_id="ts_1",
            agent_run_id="ar_1",
        )

        self.assertTrue(result["ok"])
        self.assertEqual(len(self.transport.comments), 1)
        self.assertIn("[Stage Started]", self.transport.comments[0][1])

    def test_stage_completed_template(self):
        self.transport.fail_first_comment = False
        result = self.adapter.post_stage_completed(
            task_id="task_1",
            handoff={
                "goal": "fix login",
                "completed": ["patch applied", "tests added"],
                "evidence": ["tests:pass"],
                "risks": ["needs load test"],
                "next_actions": ["tester validates"],
                "confidence": "medium",
            },
            task_session_id="ts_1",
            agent_run_id="ar_1",
        )

        self.assertTrue(result["ok"])
        body = self.transport.comments[0][1]
        self.assertIn("Goal: fix login", body)
        self.assertIn("Completed: patch applied; tests added", body)

    def test_updates_task_status(self):
        result = self.adapter.update_task_status(task_id="task_1", status="awaiting_review")

        self.assertTrue(result["ok"])
        self.assertEqual(self.transport.status_updates[0][1]["status"], "awaiting_review")


if __name__ == "__main__":
    unittest.main()
