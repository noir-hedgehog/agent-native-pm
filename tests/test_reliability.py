import unittest
from types import SimpleNamespace

from agentpm.reliability import ReliabilityExecutor
from agentpm.store import InMemoryStore


class ScenarioAgentAdapter:
    def __init__(self, outcomes):
        self.outcomes = outcomes
        self.calls = []

    def start_run(self, payload):
        profile = payload["context"]["profile"]
        attempt = payload["context"]["attempt"]
        run_id = f"run_{profile}_{attempt}"
        self.calls.append((profile, attempt, run_id))
        return SimpleNamespace(provider_run_id=run_id, provider_session_id=f"sess_{run_id}")

    def stream_events(self, provider_run_id):
        key = provider_run_id.replace("run_", "")
        if self.outcomes.get(key) == "success":
            return [{"type": "run.completed", "payload": {}}]
        return [{"type": "run.failed", "payload": {"error": "boom"}}]


class RecordingPlaneAdapter:
    def __init__(self):
        self.failed_posts = 0
        self.status_updates = []

    def post_stage_failed(self, **kwargs):
        self.failed_posts += 1
        return {"ok": True}

    def update_task_status(self, *, task_id: str, status: str):
        self.status_updates.append(status)
        return {"ok": True}


class ReliabilityExecutorTests(unittest.TestCase):
    def test_retries_primary_then_uses_backup(self):
        store = InMemoryStore()
        session, _ = store.get_or_create_session("evt:task", "proj_1", "task_1")
        outcomes = {
            "openclaw-coder-v1_0": "fail",
            "openclaw-coder-v1_1": "fail",
            "openclaw-coder-backup_0": "success",
        }
        agent = ScenarioAgentAdapter(outcomes)
        plane = RecordingPlaneAdapter()
        executor = ReliabilityExecutor(store=store, agent_adapter=agent, plane_adapter=plane)

        def execute(profile_primary, profile_backup):
            return executor.execute_with_retry_and_fallback(
                task_id="task_1",
                task_session_id=session.task_session_id,
                stage_role="coder",
                primary_profile=profile_primary,
                backup_profile=profile_backup,
                instruction="fix",
                context={"profile": None, "attempt": None},
            )

        # We fill context profile/attempt per run by wrapping _run_once input shape.
        original_run_once = executor._run_once

        def wrapped_run_once(**kwargs):
            kwargs["context"] = {
                **kwargs["context"],
                "profile": kwargs["agent_profile"],
                "attempt": kwargs["retry_index"],
            }
            return original_run_once(**kwargs)

        executor._run_once = wrapped_run_once

        result = execute("openclaw-coder-v1", "openclaw-coder-backup")

        self.assertTrue(result["completed"])
        self.assertTrue(result["used_fallback"])
        self.assertEqual(result["profile"], "openclaw-coder-backup")

    def test_marks_blocked_when_all_attempts_fail(self):
        store = InMemoryStore()
        session, _ = store.get_or_create_session("evt:task-2", "proj_1", "task_2")
        outcomes = {
            "openclaw-coder-v1_0": "fail",
            "openclaw-coder-v1_1": "fail",
            "openclaw-coder-backup_0": "fail",
        }
        agent = ScenarioAgentAdapter(outcomes)
        plane = RecordingPlaneAdapter()
        executor = ReliabilityExecutor(store=store, agent_adapter=agent, plane_adapter=plane)

        original_run_once = executor._run_once

        def wrapped_run_once(**kwargs):
            kwargs["context"] = {
                **kwargs["context"],
                "profile": kwargs["agent_profile"],
                "attempt": kwargs["retry_index"],
            }
            return original_run_once(**kwargs)

        executor._run_once = wrapped_run_once

        result = executor.execute_with_retry_and_fallback(
            task_id="task_2",
            task_session_id=session.task_session_id,
            stage_role="coder",
            primary_profile="openclaw-coder-v1",
            backup_profile="openclaw-coder-backup",
            instruction="fix",
            context={"profile": None, "attempt": None},
        )

        self.assertFalse(result["completed"])
        self.assertEqual(plane.failed_posts, 1)
        self.assertIn("blocked", plane.status_updates)
        self.assertEqual(store.get_task_session(session.task_session_id).status, "blocked")


if __name__ == "__main__":
    unittest.main()
