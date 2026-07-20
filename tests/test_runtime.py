import os
import unittest

from agentpm.adapters.dev import DevAgentAdapter, DevPlaneWritebackAdapter
from agentpm.adapters.hermes import HermesAdapter
from agentpm.runtime import build_agent_adapter_from_env, build_assignment_orchestrator_from_env, build_plane_adapter_from_env
from agentpm.store import InMemoryStore


class RuntimeFactoryTests(unittest.TestCase):
    def setUp(self):
        self.old_env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.old_env)

    def test_default_runtime_uses_dev_adapters(self):
        os.environ.pop("AGENTPM_AGENT_PROVIDER", None)
        os.environ.pop("PLANE_API_BASE_URL", None)

        self.assertIsInstance(build_agent_adapter_from_env(), DevAgentAdapter)
        self.assertIsInstance(build_plane_adapter_from_env(), DevPlaneWritebackAdapter)

        orchestrator = build_assignment_orchestrator_from_env(InMemoryStore())
        self.assertIsInstance(orchestrator.agent_adapter, DevAgentAdapter)
        self.assertIsInstance(orchestrator.plane_adapter, DevPlaneWritebackAdapter)

    def test_hermes_runtime_requires_base_url(self):
        os.environ["AGENTPM_AGENT_PROVIDER"] = "hermes"
        os.environ.pop("HERMES_BASE_URL", None)

        with self.assertRaises(ValueError):
            build_agent_adapter_from_env()

    def test_hermes_runtime_builds_adapter(self):
        os.environ["AGENTPM_AGENT_PROVIDER"] = "hermes"
        os.environ["HERMES_BASE_URL"] = "http://hermes.local"

        self.assertIsInstance(build_agent_adapter_from_env(), HermesAdapter)

    def test_mesh_settings_override_legacy_agentpm_settings(self):
        os.environ["AGENTPM_AGENT_PROVIDER"] = "hermes"
        os.environ["MESH_AGENT_PROVIDER"] = "dev"

        self.assertIsInstance(build_agent_adapter_from_env(), DevAgentAdapter)


if __name__ == "__main__":
    unittest.main()
