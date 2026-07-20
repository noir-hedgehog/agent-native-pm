import json
import tempfile
import unittest
from pathlib import Path

from agentpm.agent_accounts import AgentAccountRegistry, extract_assignee_ids
from agentpm.agent_applications import AgentApplicationStore


class AgentAccountRegistryTests(unittest.TestCase):
    def test_loads_default_agents_with_token_and_user_maps(self):
        env = {
            "PLANE_AGENT_TOKEN_MAP": json.dumps({"hekate": "hekate-token", "iris": "iris-token"}),
            "PLANE_AGENT_USER_MAP": json.dumps(
                {
                    "hekate": {"id": "user-hekate", "email": "agent-hekate@agentpm.local"},
                    "iris": {"id": "user-iris", "email": "agent-iris@agentpm.local"},
                }
            ),
            "PLANE_MCP_AGENT_ID": "iris",
        }

        registry = AgentAccountRegistry.from_env(env=env)

        self.assertEqual(registry.default_agent_id, "iris")
        self.assertEqual(registry.get().agent_id, "iris")
        self.assertEqual(registry.get("hekate").token, "hekate-token")
        self.assertEqual(registry.get("iris").plane_user_id, "user-iris")
        self.assertEqual(registry.resolve_assignee("user-hekate").agent_id, "hekate")

    def test_reads_ignored_agent_env_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / "plane-agent-env.sh"
            env_file.write_text(
                "export PLANE_AGENT_TOKEN_MAP='{\"taichi\":\"taichi-token\"}'\n"
                "export PLANE_AGENT_USER_MAP='{\"taichi\":{\"id\":\"user-taichi\"}}'\n",
                encoding="utf-8",
            )

            registry = AgentAccountRegistry.from_env(env={}, env_file=env_file)

            self.assertEqual(registry.get("taichi").token, "taichi-token")
            self.assertEqual(registry.resolve_assignee("user-taichi").agent_id, "taichi")

    def test_loads_dynamic_agents_from_registry_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry_file = Path(tmp) / "plane-agent-registry.json"
            registry_file.write_text(
                json.dumps(
                    {
                        "agents": {
                            "nova": {
                                "display_name": "Nova",
                                "email": "agent-nova@agentpm.local",
                                "role": "member",
                                "plane_user_id": "user-nova",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            registry = AgentAccountRegistry.from_env(
                env={"PLANE_AGENT_TOKEN_MAP": json.dumps({"nova": "nova-token"})},
                registry_file=registry_file,
            )

            self.assertEqual(registry.get("nova").display_name, "Nova")
            self.assertEqual(registry.get("nova").token, "nova-token")
            self.assertIn("create_work_item", registry.get("nova").capabilities)
            self.assertEqual(registry.resolve_assignee("user-nova").agent_id, "nova")

    def test_public_accounts_do_not_include_token_values(self):
        registry = AgentAccountRegistry.from_env(env={"PLANE_AGENT_TOKEN_MAP": json.dumps({"iris": "secret-token"})})

        payload = json.dumps(registry.public_accounts())

        self.assertNotIn("secret-token", payload)
        self.assertIn('"has_token": true', payload)

    def test_agent_application_store_dedupes_pending_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = AgentApplicationStore(Path(tmp) / "applications.json")

            first = store.request_registration(
                agent_id="Nova Agent",
                display_name="Nova",
                requested_role="member",
                project_id="project-1",
            )
            second = store.request_registration(
                agent_id="nova-agent",
                display_name="Nova",
                requested_role="member",
                project_id="project-1",
            )

            self.assertTrue(first["created"])
            self.assertFalse(second["created"])
            self.assertEqual(len(store.list(status="pending")), 1)
            self.assertEqual(store.list(status="pending")[0].agent_id, "nova-agent")

    def test_extracts_assignee_ids_from_plane_shapes(self):
        self.assertEqual(
            extract_assignee_ids(
                {
                    "assignee_ids": ["user-a"],
                    "assignees": [{"id": "user-b"}],
                    "assignee_details": [{"id": "user-c"}],
                }
            ),
            {"user-a", "user-b", "user-c"},
        )


if __name__ == "__main__":
    unittest.main()
