import hashlib
import hmac
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agentpm.orchestrator import AssignmentOrchestrator
from agentpm.policy import policy_input_from_payload
from agentpm.store import InMemoryStore


def sign(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


class FakeAgentAdapter:
    def __init__(self):
        self.started_payloads = []

    def start_run(self, payload):
        self.started_payloads.append(payload)
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
        self.started_roles = []
        self.progress = 0
        self.completed = 0
        self.failed = 0
        self.statuses = []

    def post_stage_started(self, **kwargs):
        self.started += 1
        self.started_roles.append(kwargs.get("stage_role"))
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

    def update_task_status(self, *, task_id: str, status: str, **kwargs):
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

    def test_plane_payload_passes_real_work_item_context(self):
        payload = {
            "event": "issue",
            "action": "update",
            "webhook_id": "wh_1",
            "workspace_id": "ws_1",
            "data": {
                "id": "task_plane_1",
                "project_id": "proj_1",
                "identifier": "AG-42",
                "name": "Investigate webhook retries",
                "description_stripped": "Find and fix duplicate agent executions",
                "assignees": [{"id": "agent_openclaw_coder"}],
            },
            "activity": {"field": "assignees"},
        }
        raw = json.dumps(payload).encode("utf-8")
        headers = {"X-Plane-Signature": sign(raw, self.secret)}

        result = self.orchestrator.process_assignment(raw_body=raw, headers=headers)

        self.assertTrue(result["completed"])
        started = self.agent.started_payloads[-1]
        self.assertEqual(started["instruction"], "Find and fix duplicate agent executions")
        self.assertEqual(started["context"]["task_title"], "Investigate webhook retries")
        self.assertEqual(started["context"]["task_key"], "AG-42")

    def test_maps_plane_agent_user_id_to_stable_agent_profile(self):
        env = {
            "PLANE_AGENT_USER_MAP": json.dumps({"iris": {"id": "plane-user-iris", "email": "agent-iris@agentpm.local"}})
        }
        with patch.dict(os.environ, env, clear=True):
            orchestrator = AssignmentOrchestrator(
                store=InMemoryStore(),
                agent_adapter=self.agent,
                plane_adapter=self.plane,
                secret=self.secret,
            )
            payload = dict(self.payload)
            payload["event_id"] = "plane_evt_iris"
            payload["assignee"] = {"id": "plane-user-iris"}
            raw = json.dumps(payload).encode("utf-8")
            headers = {"X-Plane-Signature": sign(raw, self.secret)}

            result = orchestrator.process_assignment(raw_body=raw, headers=headers)

            run = orchestrator.store.get_agent_run(result["agent_run_id"])
            self.assertEqual(run.agent_profile, "iris")
            created = [
                event
                for event in orchestrator.store.list_audit_events()
                if event.event_type == "agent_run.created"
            ][0]
            self.assertEqual(created.payload["plane_user_id"], "plane-user-iris")
            self.assertEqual(created.payload["plane_user_email"], "agent-iris@agentpm.local")

    def test_assignment_uses_project_policy_pipeline_when_available(self):
        self.store.publish_project_policy(
            policy_input_from_payload(
                "proj_1",
                {
                    "pipeline_definition": ["coder", "tester"],
                    "agent_profile_by_role": {"coder": "iris", "tester": "lingxi"},
                    "transition_approval_rules": {"coder->tester": False, "tester->done": False},
                    "transition_timeout_hours": {"reminder": 24, "block": 72},
                    "allowed_actions_by_role": {"coder": ["write_patch"], "tester": ["run_tests"]},
                    "published_by": "user-admin",
                },
            )
        )
        raw = json.dumps(self.payload).encode("utf-8")
        headers = {"X-Plane-Signature": sign(raw, self.secret)}

        result = self.orchestrator.process_assignment(raw_body=raw, headers=headers)

        self.assertTrue(result["completed"])
        self.assertEqual(result["policy_version"], 1)
        self.assertEqual(self.plane.started_roles, ["coder", "tester"])
        runs = self.store.list_agent_runs_for_session(result["task_session_id"])
        self.assertEqual([run.agent_profile for run in runs], ["iris", "lingxi"])
        self.assertIn("done", self.plane.statuses)

    def test_assignment_policy_can_pause_for_transition_approval(self):
        self.store.publish_project_policy(
            policy_input_from_payload(
                "proj_1",
                {
                    "pipeline_definition": ["coder", "tester"],
                    "agent_profile_by_role": {"coder": "iris", "tester": "lingxi"},
                    "transition_approval_rules": {"coder->tester": True, "tester->done": False},
                    "transition_timeout_hours": {"reminder": 24, "block": 72},
                    "allowed_actions_by_role": {"coder": ["write_patch"], "tester": ["run_tests"]},
                    "published_by": "user-admin",
                },
            )
        )
        raw = json.dumps({**self.payload, "event_id": "plane_evt_approval"}).encode("utf-8")
        headers = {"X-Plane-Signature": sign(raw, self.secret)}

        result = self.orchestrator.process_assignment(raw_body=raw, headers=headers)

        self.assertFalse(result["completed"])
        self.assertTrue(result["awaiting_approval"])
        self.assertEqual(self.plane.started_roles, ["coder"])
        self.assertEqual(len(self.store.list_pending_transition_approvals()), 1)

        approval = self.store.list_pending_transition_approvals()[0]
        decision = self.orchestrator.record_transition_decision(
            approval_id=approval.approval_id,
            decision="approve",
            reviewer_id="human-admin",
            note="Proceed to testing",
        )
        resumed = self.orchestrator.resume_approved_transition(approval.approval_id)

        self.assertTrue(decision["resume_queued"])
        self.assertTrue(resumed["completed"])
        self.assertEqual(self.plane.started_roles, ["coder", "tester"])
        session = self.store.get_task_session(result["task_session_id"])
        self.assertEqual(session.status, "done")


if __name__ == "__main__":
    unittest.main()
