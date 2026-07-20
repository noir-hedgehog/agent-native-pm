import unittest

from agentpm.policy import policy_input_from_payload
from agentpm.store import InMemoryStore


VALID_POLICY = {
    "pipeline_definition": ["coder", "tester", "reviewer"],
    "agent_profile_by_role": {
        "coder": "iris",
        "tester": "lingxi",
        "reviewer": "hekate",
    },
    "transition_approval_rules": {
        "coder->tester": False,
        "tester->reviewer": True,
        "reviewer->done": True,
    },
    "transition_timeout_hours": {"reminder": 24, "block": 72},
    "allowed_actions_by_role": {
        "coder": ["read_repo", "write_patch"],
        "tester": ["run_tests"],
        "reviewer": ["update_task_status"],
    },
    "published_by": "user-admin",
    "change_note": "initial policy",
}


class ProjectPolicyTests(unittest.TestCase):
    def test_validates_and_publishes_policy_versions(self):
        store = InMemoryStore()
        first = store.publish_project_policy(policy_input_from_payload("proj_1", VALID_POLICY))
        second_payload = {**VALID_POLICY, "change_note": "second policy"}
        second = store.publish_project_policy(policy_input_from_payload("proj_1", second_payload))

        self.assertEqual(first.version, 1)
        self.assertEqual(second.version, 2)
        self.assertEqual(store.get_latest_project_policy("proj_1").change_note, "second policy")
        self.assertEqual(len(store.list_project_policy_versions("proj_1")), 2)

    def test_rejects_invalid_transition_key(self):
        payload = {**VALID_POLICY, "transition_approval_rules": {"coder->reviewer": True}}

        with self.assertRaises(ValueError):
            policy_input_from_payload("proj_1", payload)

    def test_rejects_duplicate_roles(self):
        payload = {**VALID_POLICY, "pipeline_definition": ["coder", "coder"]}

        with self.assertRaises(ValueError):
            policy_input_from_payload("proj_1", payload)

    def test_rejects_invalid_timeout_order(self):
        payload = {**VALID_POLICY, "transition_timeout_hours": {"reminder": 72, "block": 24}}

        with self.assertRaises(ValueError):
            policy_input_from_payload("proj_1", payload)

    def test_rejects_non_positive_timeout(self):
        payload = {**VALID_POLICY, "transition_timeout_hours": {"reminder": 0, "block": 24}}

        with self.assertRaises(ValueError):
            policy_input_from_payload("proj_1", payload)

    def test_rejects_empty_role_actions(self):
        payload = {
            **VALID_POLICY,
            "allowed_actions_by_role": {
                "coder": ["read_repo"],
                "tester": [],
                "reviewer": ["update_task_status"],
            },
        }

        with self.assertRaises(ValueError):
            policy_input_from_payload("proj_1", payload)


if __name__ == "__main__":
    unittest.main()
