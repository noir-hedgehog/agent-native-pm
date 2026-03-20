import unittest
from types import SimpleNamespace

from agentpm.pipeline import SerialPipelineExecutor
from agentpm.store import InMemoryStore


class DeterministicAgentAdapter:
    def __init__(self):
        self.start_calls = []

    def start_run(self, payload):
        self.start_calls.append(payload)
        role = payload["stage_role"]
        return SimpleNamespace(provider_run_id=f"run_{role}", provider_session_id=f"sess_{role}")

    def stream_events(self, provider_run_id):
        role = provider_run_id.replace("run_", "")
        return [
            {"type": "run.progress", "payload": {"summary": f"{role} working"}},
            {
                "type": "run.completed",
                "payload": {
                    "handoff_hint": {
                        "goal": f"finish {role}",
                        "completed": [f"{role} done"],
                        "evidence": [f"{role}:evidence"],
                        "risks": [],
                        "next_actions": [f"next after {role}"],
                        "confidence": "high",
                    }
                },
            },
        ]


class RecordingPlaneAdapter:
    def __init__(self):
        self.started_roles = []
        self.progress_roles = []
        self.completed_count = 0
        self.status_updates = []

    def post_stage_started(self, **kwargs):
        self.started_roles.append(kwargs["stage_role"])
        return {"ok": True}

    def post_stage_progress(self, **kwargs):
        self.progress_roles.append(kwargs["stage_role"])
        return {"ok": True}

    def post_stage_completed(self, **kwargs):
        self.completed_count += 1
        return {"ok": True}

    def post_stage_failed(self, **kwargs):
        return {"ok": True}

    def update_task_status(self, *, task_id: str, status: str):
        self.status_updates.append(status)
        return {"ok": True}


class SerialPipelineExecutorTests(unittest.TestCase):
    def test_pipeline_runs_in_deterministic_order_and_passes_handoff(self):
        store = InMemoryStore()
        session, _ = store.get_or_create_session("evt:task", "proj_1", "task_1")
        agent = DeterministicAgentAdapter()
        plane = RecordingPlaneAdapter()
        executor = SerialPipelineExecutor(store=store, agent_adapter=agent, plane_adapter=plane)

        result = executor.execute(
            task_session_id=session.task_session_id,
            task_id="task_1",
            task={"title": "Task", "description": "Desc", "key": "AG-1"},
            pipeline_roles=["coder", "tester", "reviewer"],
            agent_profile_by_role={
                "coder": "openclaw-coder-v1",
                "tester": "openclaw-tester-v1",
                "reviewer": "openclaw-reviewer-v1",
            },
        )

        self.assertTrue(result["completed"])
        self.assertEqual(plane.started_roles, ["coder", "tester", "reviewer"])
        self.assertEqual(plane.completed_count, 3)
        self.assertIn("awaiting_review", plane.status_updates)

        self.assertIsNone(agent.start_calls[0]["context"]["previous_handoff"])
        self.assertEqual(
            agent.start_calls[1]["context"]["previous_handoff"]["goal"],
            "finish coder",
        )
        self.assertEqual(
            agent.start_calls[2]["context"]["previous_handoff"]["goal"],
            "finish tester",
        )

        for run_id in result["agent_run_ids"]:
            run = store.get_agent_run(run_id)
            self.assertEqual(run.status, "succeeded")
            self.assertIsNotNone(store.get_handoff_contract(run_id))


if __name__ == "__main__":
    unittest.main()
