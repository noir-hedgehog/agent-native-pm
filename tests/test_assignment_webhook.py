import hashlib
import hmac
import json
import unittest

from agentpm.errors import InvalidPayloadError, InvalidSignatureError
from agentpm.store import InMemoryStore
from agentpm.webhook import handle_assignment_webhook


def sign(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


class AssignmentWebhookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.secret = "test-secret"
        self.store = InMemoryStore()
        self.payload = {
            "event_id": "plane_evt_123",
            "event_type": "task.assigned",
            "project": {"id": "proj_1"},
            "task": {"id": "task_1", "key": "AG-1"},
            "assignee": {"id": "agent_openclaw_coder"},
            "actor": {"id": "user_1"},
        }

    def test_accepts_valid_assignment(self) -> None:
        raw = json.dumps(self.payload).encode("utf-8")
        headers = {"X-Plane-Signature": sign(raw, self.secret)}

        status, response = handle_assignment_webhook(
            raw_body=raw,
            headers=headers,
            secret=self.secret,
            store=self.store,
        )

        self.assertEqual(status, 202)
        self.assertTrue(response["accepted"])
        self.assertFalse(response["duplicate"])
        self.assertEqual(response["idempotency_key"], "plane_evt_123:task_1")

    def test_dedupes_duplicate_delivery(self) -> None:
        raw = json.dumps(self.payload).encode("utf-8")
        headers = {"X-Plane-Signature": sign(raw, self.secret)}

        _, first = handle_assignment_webhook(raw_body=raw, headers=headers, secret=self.secret, store=self.store)
        _, second = handle_assignment_webhook(raw_body=raw, headers=headers, secret=self.secret, store=self.store)

        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(first["task_session_id"], second["task_session_id"])

    def test_rejects_invalid_signature(self) -> None:
        raw = json.dumps(self.payload).encode("utf-8")
        headers = {"X-Plane-Signature": "sha256=deadbeef"}

        with self.assertRaises(InvalidSignatureError):
            handle_assignment_webhook(raw_body=raw, headers=headers, secret=self.secret, store=self.store)

    def test_rejects_invalid_payload(self) -> None:
        raw = json.dumps({"event_id": "x"}).encode("utf-8")
        headers = {"X-Plane-Signature": sign(raw, self.secret)}

        with self.assertRaises(InvalidPayloadError):
            handle_assignment_webhook(raw_body=raw, headers=headers, secret=self.secret, store=self.store)


if __name__ == "__main__":
    unittest.main()
