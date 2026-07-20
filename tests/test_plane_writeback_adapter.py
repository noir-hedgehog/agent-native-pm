import unittest

from agentpm.adapters.plane import HttpPlaneTransport, PlaneWritebackAdapter


class FlakyFakePlaneTransport:
    def __init__(self):
        self.comments = []
        self.status_updates = []
        self.fail_first_comment = True

    def post_comment(self, task_id, body, **context):
        if self.fail_first_comment:
            self.fail_first_comment = False
            raise RuntimeError("temporary failure")
        self.comments.append((task_id, body, context))
        return {"ok": True, "task_id": task_id, "body": body}

    def patch_task(self, task_id, payload, **context):
        self.status_updates.append((task_id, payload, context))
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
        self.assertEqual(self.transport.comments[0][2]["agent_run_id"], "ar_1")

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

    def test_http_transport_renders_real_plane_paths_and_payloads(self):
        class RecordingHttpPlaneTransport(HttpPlaneTransport):
            def __init__(self):
                super().__init__(
                    base_url="http://plane.local",
                    token="token",
                    workspace_slug="acme",
                    project_id="proj_default",
                    status_field="state",
                    status_map={"awaiting_review": "state_review_uuid"},
                )
                self.requests = []

            def _request(self, method, path, payload):
                self.requests.append((method, path, payload))
                return {"ok": True, "path": path, "payload": payload}

        transport = RecordingHttpPlaneTransport()

        comment = transport.post_comment(
            "issue_1",
            "hello",
            project_id="proj_1",
            agent_run_id="ar_1",
        )
        self.assertEqual(
            comment["path"],
            "/api/v1/workspaces/acme/projects/proj_1/work-items/issue_1/comments/",
        )
        self.assertEqual(comment["payload"]["comment_html"], "hello")
        self.assertEqual(comment["payload"]["external_source"], "agentpm")
        self.assertTrue(comment["payload"]["external_id"].startswith("ar_1:"))

        status = transport.patch_task("issue_1", {"status": "awaiting_review"}, project_id="proj_1")
        self.assertEqual(
            status["path"],
            "/api/v1/workspaces/acme/projects/proj_1/work-items/issue_1/",
        )
        self.assertEqual(status["payload"]["state"], "state_review_uuid")

    def test_http_transport_uses_plane_api_key_header(self):
        class RecordingHeaderTransport(HttpPlaneTransport):
            def __init__(self):
                super().__init__(
                    base_url="http://plane.local",
                    token="plane_api_123",
                    workspace_slug="acme",
                    project_id="proj_1",
                )
                self.headers = None

            def _request(self, method, path, payload):
                import urllib.request

                body = "{}".encode("utf-8")
                req = urllib.request.Request(
                    url=f"{self.base_url}{path}",
                    data=body,
                    headers={"Content-Type": "application/json", self.api_key_header: self.token},
                    method=method,
                )
                self.headers = dict(req.header_items())
                return {"ok": True}

        transport = RecordingHeaderTransport()
        transport.post_comment("issue_1", "hello")
        self.assertEqual(transport.headers["X-api-key"], "plane_api_123")


if __name__ == "__main__":
    unittest.main()
