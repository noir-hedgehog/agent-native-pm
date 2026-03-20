import os
import unittest

from agentpm.adapters.openclaw import OpenClawAdapter, OpenClawAdapterConfig


class FakeTransport:
    def __init__(self) -> None:
        self.calls = []

    def post(self, path, payload):
        self.calls.append(("POST", path, payload))
        if path == "/runs":
            return {
                "run_id": "oc_run_123",
                "session_id": "oc_sess_123",
                "status": "pending",
                "started_at": "2026-03-20T01:00:00Z",
            }
        if path.endswith("/messages"):
            return {"accepted": True, "queued_at": "2026-03-20T01:01:00Z"}
        if path.endswith("/cancel"):
            return {"status": "canceled", "canceled_at": "2026-03-20T01:02:00Z"}
        return {}

    def get(self, path):
        self.calls.append(("GET", path, None))
        if path == "/runs/oc_run_123":
            return {
                "run_id": "oc_run_123",
                "session_id": "oc_sess_123",
                "status": "in_progress",
                "progress": {"summary": "working", "percent": 50},
                "updated_at": "2026-03-20T01:03:00Z",
            }
        if path == "/runs/oc_run_123/events":
            return {
                "events": [
                    {
                        "id": "evt_1",
                        "type": "message",
                        "session_id": "oc_sess_123",
                        "occurred_at": "2026-03-20T01:04:00Z",
                        "payload": {"content": "hello"},
                    },
                    {
                        "id": "evt_2",
                        "type": "completed",
                        "session_id": "oc_sess_123",
                        "occurred_at": "2026-03-20T01:05:00Z",
                        "payload": {"result": "done"},
                    },
                ]
            }
        return {}


class OpenClawAdapterTests(unittest.TestCase):
    def setUp(self):
        self.transport = FakeTransport()
        self.adapter = OpenClawAdapter(self.transport)

    def test_start_run_normalizes_pending_to_queued(self):
        result = self.adapter.start_run(
            {
                "task_session_id": "ts_1",
                "agent_run_id": "ar_1",
                "task_id": "task_1",
                "stage_role": "coder",
                "instruction": "Fix bug",
                "context": {"task_title": "Bug"},
                "policy": {"max_retry": 1},
            }
        )

        self.assertEqual(result.provider, "openclaw")
        self.assertEqual(result.provider_run_id, "oc_run_123")
        self.assertEqual(result.status, "queued")

    def test_get_run_normalizes_status_and_progress(self):
        run = self.adapter.get_run("oc_run_123")

        self.assertEqual(run["status"], "running")
        self.assertEqual(run["progress"]["percent"], 50)

    def test_cancel_run_normalizes_status(self):
        result = self.adapter.cancel_run("oc_run_123")
        self.assertEqual(result["status"], "canceled")

    def test_stream_events_maps_provider_types(self):
        events = self.adapter.stream_events("oc_run_123")

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["type"], "run.output")
        self.assertEqual(events[1]["type"], "run.completed")

    def test_supports_alternate_run_and_session_keys(self):
        class AltTransport(FakeTransport):
            def post(self, path, payload):
                if path == "/v2/runs":
                    return {
                        "id": "run_alt_1",
                        "sessionId": "sess_alt_1",
                        "state": "running",
                    }
                return super().post(path, payload)

        config = OpenClawAdapterConfig(
            start_run_path="/v2/runs",
            run_id_key="run_id_missing",
            session_id_key="session_id_missing",
            status_key="state",
        )
        adapter = OpenClawAdapter(AltTransport(), config=config)
        result = adapter.start_run(
            {
                "task_session_id": "ts_1",
                "agent_run_id": "ar_1",
                "task_id": "task_1",
                "stage_role": "coder",
                "instruction": "Fix bug",
                "context": {"task_title": "Bug"},
                "policy": {"max_retry": 1},
            }
        )
        self.assertEqual(result.provider_run_id, "run_alt_1")
        self.assertEqual(result.provider_session_id, "sess_alt_1")
        self.assertEqual(result.status, "running")

    def test_config_can_be_built_from_env(self):
        old = dict(os.environ)
        try:
            os.environ["OPENCLAW_START_RUN_PATH"] = "/api/runs/start"
            os.environ["OPENCLAW_RUN_ID_KEY"] = "id"
            cfg = OpenClawAdapterConfig.from_env()
            self.assertEqual(cfg.start_run_path, "/api/runs/start")
            self.assertEqual(cfg.run_id_key, "id")
        finally:
            os.environ.clear()
            os.environ.update(old)


if __name__ == "__main__":
    unittest.main()
