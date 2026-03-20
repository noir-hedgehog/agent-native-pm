import hashlib
import hmac
import json
import unittest
from types import SimpleNamespace

from agentpm.orchestrator import AssignmentOrchestrator
from agentpm.store import InMemoryStore


def sign(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


class FakeAgentAdapter:
    def start_run(self, payload):
        return SimpleNamespace(
            provider="openclaw",
            provider_run_id="oc_run_1",
            provider_session_id="oc_sess_1",
            status="queued",
        )

    def stream_events(self, provider_run_id):
        return [
            {
                "type": "run.progress",
                "payload": {"summary": "analyzing"},
            },
            {
                "type": "run.completed",
                "payload": {
                    "handoff_hint": {
                        "goal": "fix timeout",
                        "completed": ["patch merged"],
                        "evidence": ["tests:pass"],
                        "risks": ["need canary"],
                        "next_actions": ["tester verifies"],
                        "confidence": "high",
                    }
                },
            },
        ]


class FakePlaneAdapter:
    def __init__(self):
        self.started = 0
        self.progress = 0
        self.completed = 0
        self.failed = 0
        self.statuses = []

    def post_stage_started(self, **kwargs):
        self.started += 1
        return {"ok": True}

    def post_stage_progress(self, **kwargs):
        self.progress += 1
        return {"ok": True}

    def post_stage_completed(self, **kwargs):
        self.completed += 1
        return {"ok": True}

    def post_stage_failed(self, **kwargs):
        self.failed += 1
        return {"ok": True}

    def update_task_status(self, *, task_id: str, status: str):
        self.statuses.append(status)
        return {"ok": True}


class AssignmentOrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.secret = "test-secret"
        self.store = InMemoryStore()
        self.agent = FakeAgentAdapter()
        self.plane = FakePlaneAdapter()
        self.orchestrator = AssignmentOrchestrator(
            store=self.store,
            agent_adapter=self.agent,
            plane_adapter=self.plane,
            secret=self.secret,
        )
        self.payload = {
            "event_id": "plane_evt_123",
            "event_type": "task.assigned",
            "project": {"id": "proj_1"},
            "task": {
                "id": "task_1",
                "key": "AG-1",
                "title": "Fix login timeout",
                "description": "Fix mobile token refresh timeout",
            },
            "assignee": {"id": "agent_openclaw_coder"},
            "actor": {"id": "user_1"},
        }

    def test_single_agent_e2e_flow_completes(self):
        raw = json.dumps(self.payload).encode("utf-8")
        headers = {"X-Plane-Signature": sign(raw, self.secret)}

        result = self.orchestrator.process_assignment(raw_body=raw, headers=headers)

        self.assertTrue(result["accepted"])
        self.assertFalse(result["duplicate"])
        self.assertTrue(result["completed"])
        self.assertEqual(self.plane.started, 1)
        self.assertEqual(self.plane.progress, 1)
        self.assertEqual(self.plane.completed, 1)
        self.assertEqual(self.plane.failed, 0)
        self.assertIn("awaiting_review", self.plane.statuses)

        run = self.store.get_agent_run(result["agent_run_id"])
        self.assertIsNotNone(run)
        self.assertEqual(run.status, "succeeded")

        contract = self.store.get_handoff_contract(result["agent_run_id"])
        self.assertIsNotNone(contract)
        self.assertEqual(contract.goal, "fix timeout")

        events = self.store.list_audit_events()
        event_types = [e.event_type for e in events]
        self.assertIn("agent_run.created", event_types)
        self.assertIn("agent_run.started", event_types)
        self.assertIn("agent_run.completed", event_types)

    def test_duplicate_delivery_skips_second_run(self):
        raw = json.dumps(self.payload).encode("utf-8")
        headers = {"X-Plane-Signature": sign(raw, self.secret)}

        first = self.orchestrator.process_assignment(raw_body=raw, headers=headers)
        second = self.orchestrator.process_assignment(raw_body=raw, headers=headers)

        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertIsNone(second["agent_run_id"])


if __name__ == "__main__":
    unittest.main()
