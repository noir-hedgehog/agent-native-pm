import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "scripts"))

import plane_mcp_server


class RecordingPlaneClient:
    instances = []
    work_item = {"assignee_ids": []}

    def __init__(self, config):
        self.config = config
        self.calls = []
        RecordingPlaneClient.instances.append(self)

    def list_projects(self):
        self.calls.append(("list_projects",))
        return {"results": []}

    def list_states(self, project_id=None):
        self.calls.append(("list_states", project_id))
        return {"results": []}

    def list_work_items(self, **kwargs):
        self.calls.append(("list_work_items", kwargs))
        return {"results": []}

    def compact_work_items(self, payload, *, limit=50):
        return []

    def get_work_item(self, work_item_id, *, project_id=None):
        self.calls.append(("get_work_item", work_item_id, project_id))
        return dict(RecordingPlaneClient.work_item)

    def summarize_work_item(self, work_item_id, *, project_id=None):
        self.calls.append(("summarize_work_item", work_item_id, project_id))
        return {"work_item": {"id": work_item_id}, "recent_comments": []}

    def add_comment(self, work_item_id, body, *, project_id=None):
        self.calls.append(("add_comment", work_item_id, body, project_id))
        return {"ok": True, "token": self.config.api_token}

    def update_work_item_status(self, work_item_id, status, *, project_id=None):
        self.calls.append(("update_status", work_item_id, status, project_id))
        return {"ok": True, "token": self.config.api_token}

    def assign_work_item(self, work_item_id, assignee_id, *, project_id=None):
        self.calls.append(("assign_work_item", work_item_id, assignee_id, project_id))
        return {"ok": True, "assignee_id": assignee_id, "token": self.config.api_token}

    def create_project(self, **kwargs):
        self.calls.append(("create_project", kwargs))
        return {"id": "project-new", **kwargs, "token": self.config.api_token}

    def add_project_member(self, project_id, member_id, role):
        self.calls.append(("add_project_member", project_id, member_id, role))
        return {"project_id": project_id, "member_id": member_id, "role": role}

    def create_work_item(self, **kwargs):
        self.calls.append(("create_work_item", kwargs))
        return {"id": "issue-new", **kwargs, "token": self.config.api_token}


def mcp_env():
    return {
        "PLANE_API_BASE_URL": "http://plane.local",
        "PLANE_WORKSPACE_SLUG": "agentpm",
        "PLANE_PROJECT_ID": "project-1",
        "PLANE_AGENT_TOKEN_MAP": json.dumps(
            {
                "hekate": "hekate-token",
                "iris": "iris-token",
                "lingxi": "lingxi-token",
                "taichi": "taichi-token",
            }
        ),
        "PLANE_AGENT_USER_MAP": json.dumps(
            {
                "hekate": {"id": "user-hekate"},
                "iris": {"id": "user-iris"},
                "lingxi": {"id": "user-lingxi"},
                "taichi": {"id": "user-taichi"},
            }
        ),
    }


class PlaneMcpServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.registry_file = Path(self.tmp.name) / "registry.json"
        self.applications_file = Path(self.tmp.name) / "applications.json"
        self.registry_file.write_text(
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
        RecordingPlaneClient.instances = []
        RecordingPlaneClient.work_item = {"assignee_ids": []}
        self.env_patch = patch.dict(
            os.environ,
            {
                **mcp_env(),
                "PLANE_AGENT_TOKEN_MAP": json.dumps(
                    {
                        "hekate": "hekate-token",
                        "iris": "iris-token",
                        "lingxi": "lingxi-token",
                        "taichi": "taichi-token",
                        "nova": "nova-token",
                    }
                ),
                "AGENTPM_PLANE_AGENT_REGISTRY_FILE": str(self.registry_file),
                "AGENTPM_PLANE_AGENT_APPLICATIONS_FILE": str(self.applications_file),
            },
            clear=True,
        )
        self.client_patch = patch.object(plane_mcp_server, "PlaneClient", RecordingPlaneClient)
        self.env_patch.start()
        self.client_patch.start()

    def tearDown(self):
        self.client_patch.stop()
        self.env_patch.stop()
        self.tmp.cleanup()

    def make_server(self):
        return plane_mcp_server.PlaneMcpServer()

    def test_selects_token_for_agent_id(self):
        server = self.make_server()

        server._list_work_items({"agent_id": "iris"})

        self.assertEqual(RecordingPlaneClient.instances[-1].config.api_token, "iris-token")

    def test_locked_mcp_server_rejects_other_agent_id(self):
        self.env_patch.stop()
        self.env_patch = patch.dict(
            os.environ,
            {
                **mcp_env(),
                "PLANE_MCP_LOCKED_AGENT_ID": "iris",
                "AGENTPM_PLANE_AGENT_REGISTRY_FILE": str(self.registry_file),
                "AGENTPM_PLANE_AGENT_APPLICATIONS_FILE": str(self.applications_file),
            },
            clear=True,
        )
        self.env_patch.start()
        server = self.make_server()

        server._list_work_items({})
        self.assertEqual(RecordingPlaneClient.instances[-1].config.api_token, "iris-token")

        with self.assertRaises(PermissionError):
            server._list_work_items({"agent_id": "hekate"})

    def test_list_agent_accounts_never_returns_token_values(self):
        server = self.make_server()

        result = server._list_agent_accounts({"agent_id": "hekate"})
        payload = json.dumps(result)

        self.assertIn('"agent_id": "iris"', payload)
        self.assertIn('"agent_id": "nova"', payload)
        self.assertIn('"has_token": true', payload)
        self.assertNotIn("iris-token", payload)
        self.assertNotIn("hekate-token", payload)
        self.assertNotIn("nova-token", payload)

    def test_bootstrap_registration_request_does_not_need_agent_token(self):
        server = self.make_server()

        result = server._request_agent_registration(
            {"agent_id": "atlas", "display_name": "Atlas", "requested_role": "member", "project_id": "project-1"}
        )
        second = server._request_agent_registration(
            {"agent_id": "atlas", "display_name": "Atlas", "requested_role": "member", "project_id": "project-1"}
        )

        self.assertTrue(result["created"])
        self.assertFalse(second["created"])
        self.assertEqual(result["application"]["status"], "pending")

    def test_unknown_agent_cannot_use_registered_tools(self):
        server = self.make_server()

        with self.assertRaises(ValueError):
            server._list_projects({"agent_id": "atlas"})

    def test_taichi_cannot_update_status(self):
        server = self.make_server()

        with self.assertRaises(PermissionError):
            server._update_status({"agent_id": "taichi", "work_item_id": "issue-1", "status": "done"})

    def test_member_agent_can_only_update_assigned_work_item(self):
        server = self.make_server()

        with self.assertRaises(PermissionError):
            server._update_status({"agent_id": "iris", "work_item_id": "issue-1", "status": "done"})

        RecordingPlaneClient.work_item = {"assignee_ids": ["user-iris"]}
        result = server._update_status({"agent_id": "iris", "work_item_id": "issue-1", "status": "done"})

        self.assertTrue(result["ok"])
        self.assertEqual(result["token"], "iris-token")

    def test_hekate_can_assign_member_agent(self):
        server = self.make_server()

        result = server._assign_work_item(
            {"agent_id": "hekate", "work_item_id": "issue-1", "target_agent_id": "lingxi"}
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["assignee_id"], "user-lingxi")
        self.assertEqual(result["token"], "hekate-token")

    def test_dynamic_member_agent_can_create_work_item(self):
        server = self.make_server()

        result = server._create_work_item(
            {
                "agent_id": "nova",
                "project_id": "project-1",
                "name": "Dynamic task",
                "target_agent_id": "iris",
            }
        )

        self.assertEqual(result["token"], "nova-token")
        self.assertEqual(result["assignee_id"], "user-iris")

    def test_guest_agent_cannot_create_work_item(self):
        server = self.make_server()

        with self.assertRaises(PermissionError):
            server._create_work_item(
                {
                    "agent_id": "taichi",
                    "project_id": "project-1",
                    "name": "Guest task",
                    "target_agent_id": "iris",
                }
            )

    def test_hekate_can_create_project_with_dynamic_members(self):
        server = self.make_server()

        result = server._create_project(
            {
                "agent_id": "hekate",
                "name": "Agent Project",
                "identifier": "AGT",
                "member_agent_ids": ["nova", "taichi"],
            }
        )

        self.assertEqual(result["project"]["token"], "hekate-token")
        self.assertEqual(result["added_members"][0]["member_id"], "user-nova")
        self.assertEqual(result["added_members"][0]["role"], 15)
        self.assertEqual(result["added_members"][1]["role"], 5)

    def test_hekate_cannot_assign_guest_agent(self):
        server = self.make_server()

        with self.assertRaises(PermissionError):
            server._assign_work_item(
                {"agent_id": "hekate", "work_item_id": "issue-1", "target_agent_id": "taichi"}
            )

    def test_get_project_policy_uses_agentpm_api(self):
        server = self.make_server()

        with patch.object(plane_mcp_server, "_agentpm_request", return_value={"policy": {"version": 1}}) as request:
            result = server._get_project_policy({"agent_id": "iris", "project_id": "project-1"})

        self.assertEqual(result["policy"]["version"], 1)
        request.assert_called_once_with("GET", "http://127.0.0.1:8080/policies/projects/project-1")

    def test_hekate_can_publish_project_policy(self):
        server = self.make_server()
        policy = {
            "pipeline_definition": ["coder"],
            "agent_profile_by_role": {"coder": "iris"},
            "transition_approval_rules": {"coder->done": False},
            "transition_timeout_hours": {"reminder": 24, "block": 72},
            "allowed_actions_by_role": {"coder": ["read_plane"]},
            "published_by": "hekate",
        }

        with patch.object(plane_mcp_server, "_agentpm_request", return_value={"policy": {"version": 1}}) as request:
            result = server._publish_project_policy(
                {"agent_id": "hekate", "project_id": "project-1", "policy": policy}
            )

        self.assertEqual(result["policy"]["version"], 1)
        request.assert_called_once_with("POST", "http://127.0.0.1:8080/policies/projects/project-1", policy)

    def test_member_agent_cannot_publish_project_policy(self):
        server = self.make_server()

        with self.assertRaises(PermissionError):
            server._publish_project_policy(
                {
                    "agent_id": "iris",
                    "project_id": "project-1",
                    "policy": {"pipeline_definition": ["coder"]},
                }
            )


if __name__ == "__main__":
    unittest.main()
