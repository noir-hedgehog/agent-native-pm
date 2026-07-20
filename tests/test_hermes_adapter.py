import os
import unittest

from agentpm.adapters.hermes import HermesAdapter, HermesAdapterConfig


class FakeHermesTransport:
    def post(self, path, payload):
        if path == "/sessions":
            return {"id": "hm_run_1", "sessionId": "hm_session_1", "state": "running"}
        if path.endswith("/cancel"):
            return {"state": "cancelled"}
        return {"accepted": True}

    def get(self, path):
        if path == "/sessions/hm_run_1":
            return {"id": "hm_run_1", "sessionId": "hm_session_1", "state": "completed"}
        if path == "/sessions/hm_run_1/events":
            return {
                "data": [
                    {"id": "evt_1", "event": "message", "payload": {"content": "working"}},
                    {"id": "evt_2", "event": "completed", "payload": {"handoff_hint": {"goal": "done"}}},
                ]
            }
        return {}


class HermesAdapterTests(unittest.TestCase):
    def test_hermes_adapter_uses_provider_name_and_config_mapping(self):
        adapter = HermesAdapter(
            FakeHermesTransport(),
            HermesAdapterConfig(
                start_run_path="/sessions",
                get_run_path="/sessions/{provider_run_id}",
                stream_events_path="/sessions/{provider_run_id}/events",
                cancel_run_path="/sessions/{provider_run_id}/cancel",
                run_id_key="run_id_missing",
                session_id_key="session_id_missing",
                status_key="state",
                events_key="data",
            ),
        )

        started = adapter.start_run(
            {
                "task_session_id": "ts_1",
                "agent_run_id": "ar_1",
                "task_id": "task_1",
                "stage_role": "coder",
                "instruction": "Fix bug",
                "context": {},
                "policy": {},
            }
        )
        self.assertEqual(started.provider, "hermes")
        self.assertEqual(started.provider_run_id, "hm_run_1")
        self.assertEqual(started.status, "running")

        run = adapter.get_run("hm_run_1")
        self.assertEqual(run["provider"], "hermes")
        self.assertEqual(run["status"], "succeeded")

        events = adapter.stream_events("hm_run_1")
        self.assertEqual(events[0]["provider"], "hermes")
        self.assertEqual(events[0]["type"], "run.output")
        self.assertEqual(events[1]["type"], "run.completed")

    def test_config_can_be_built_from_env(self):
        old = dict(os.environ)
        try:
            os.environ["HERMES_START_RUN_PATH"] = "/api/hermes/runs"
            os.environ["HERMES_RUN_ID_KEY"] = "id"
            cfg = HermesAdapterConfig.from_env()
            self.assertEqual(cfg.start_run_path, "/api/hermes/runs")
            self.assertEqual(cfg.run_id_key, "id")
        finally:
            os.environ.clear()
            os.environ.update(old)


if __name__ == "__main__":
    unittest.main()
