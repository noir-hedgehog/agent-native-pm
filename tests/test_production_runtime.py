import json
import subprocess
import unittest
from unittest.mock import patch

from agentpm.server import _allowed_origin
from scripts.openclaw_bridge import extract_text, safe_subprocess_error, select_agent
from scripts.plane_native_mcp_proxy import token_for_agent


class ProductionRuntimeTests(unittest.TestCase):
    def test_cors_allows_only_configured_origins(self):
        with patch.dict("os.environ", {"AGENTPM_ALLOWED_ORIGINS": "http://plane.test,http://100.64.0.1"}):
            self.assertEqual(_allowed_origin("http://plane.test"), "http://plane.test")
            self.assertIsNone(_allowed_origin("https://untrusted.test"))

    def test_native_proxy_selects_locked_agent_token(self):
        env = {"PLANE_AGENT_TOKEN_MAP": json.dumps({"iris": "secret-iris", "hekate": {"token": "secret-hekate"}})}
        self.assertEqual(token_for_agent(env, "iris"), "secret-iris")
        self.assertEqual(token_for_agent(env, "hekate"), "secret-hekate")
        with self.assertRaises(KeyError):
            token_for_agent(env, "taichi")

    def test_openclaw_bridge_uses_explicit_agent_and_extracts_payload(self):
        with patch.dict("os.environ", {"OPENCLAW_BRIDGE_ROLE_MAP": '{"coder":"iris"}'}):
            self.assertEqual(select_agent({"agent_id": "lingxi"}), "lingxi")
            self.assertEqual(select_agent({"metadata": {"stage_role": "coder"}}), "iris")
        output = extract_text({"result": {"payloads": [{"text": "Completed task"}]}})
        self.assertEqual(output, "Completed task")

    def test_openclaw_bridge_reports_provider_errors_without_tokens(self):
        error = subprocess.CalledProcessError(
            1,
            ["openclaw"],
            stderr="quota exhausted for plane_api_secret and Bearer provider-secret",
        )

        message = safe_subprocess_error(error)

        self.assertIn("quota exhausted", message)
        self.assertNotIn("plane_api_secret", message)
        self.assertNotIn("provider-secret", message)


if __name__ == "__main__":
    unittest.main()
