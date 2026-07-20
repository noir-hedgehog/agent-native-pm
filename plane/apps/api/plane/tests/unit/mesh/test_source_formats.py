# Copyright (c) 2026-present Mesh contributors
# SPDX-License-Identifier: AGPL-3.0-only

import pytest

from plane.mesh.source_formats import parse_loop_yaml, parse_project_policy_yaml, parse_skill_markdown


def test_skill_markdown_round_trip_contract():
    parsed = parse_skill_markdown(
        """---
name: bug-fix
description: Fix and verify a defect
version: 1.2.0
capabilities:
  - code.write
---
# Bug fix

Reproduce, patch, and verify the defect.
"""
    )

    assert parsed.manifest["name"] == "bug-fix"
    assert parsed.manifest["version"] == "1.2.0"
    assert parsed.body.startswith("# Bug fix")
    assert len(parsed.checksum) == 64


@pytest.mark.parametrize(
    "source,error",
    [
        ("# Missing manifest", "front matter"),
        ("---\nname: x\ndescription: y\nversion: latest\n---\nBody", "semantic versioning"),
        ("---\nname: x\ndescription: y\n---\n", "Markdown body"),
    ],
)
def test_skill_markdown_rejects_invalid_sources(source, error):
    with pytest.raises(ValueError, match=error):
        parse_skill_markdown(source)


def test_loop_yaml_accepts_agent_native_graph():
    graph = parse_loop_yaml(
        """schema_version: 1
name: Bug fix
nodes:
  - id: reported
    type: trigger
  - id: repair
    type: stage
    objective: Reproduce and repair the defect
    roles: [developer]
    required_capabilities: [code.write]
  - id: handoff
    type: handoff
  - id: verified
    type: complete
edges:
  - from: reported
    to: repair
  - from: repair
    to: handoff
  - from: handoff
    to: verified
"""
    )

    assert graph["nodes"][1]["roles"] == ["developer"]


def test_loop_yaml_rejects_prescribed_skill_or_knowledge():
    with pytest.raises(ValueError, match="cannot prescribe"):
        parse_loop_yaml(
            """schema_version: 1
name: Too rigid
nodes:
  - id: start
    type: trigger
  - id: work
    type: stage
    objective: Work
    roles: [developer]
    skill: fixed-sop
  - id: done
    type: complete
edges:
  - from: start
    to: work
  - from: work
    to: done
"""
        )


def test_loop_yaml_requires_cycle_limit():
    with pytest.raises(ValueError, match="max_transitions"):
        parse_loop_yaml(
            """schema_version: 1
name: Review loop
nodes:
  - id: start
    type: trigger
  - id: review
    type: stage
    objective: Review
    roles: [reviewer]
  - id: done
    type: complete
edges:
  - from: start
    to: review
  - from: review
    to: review
  - from: review
    to: done
"""
        )


def test_loop_yaml_validates_wait_duration():
    with pytest.raises(ValueError, match="duration_seconds"):
        parse_loop_yaml(
            """schema_version: 1
name: Delayed review
nodes:
  - id: start
    type: trigger
  - id: pause
    type: wait
    duration_seconds: soon
  - id: done
    type: complete
edges:
  - from: start
    to: pause
  - from: pause
    to: done
"""
        )


def test_project_policy_validates_roles_handoffs_and_delegation():
    policy = parse_project_policy_yaml(
        """schema_version: 1
roles:
  developer:
    capabilities: [code.write]
  reviewer:
    capabilities: [review.approve]
allowed_handoffs:
  developer: [reviewer]
  reviewer: []
delegation:
  max_depth: 2
budgets:
  default_tokens: 12000
approvals:
  production: human_admin
""",
        known_role_keys={"developer", "reviewer"},
    )

    assert policy["delegation"]["max_depth"] == 2


def test_project_policy_rejects_unknown_role():
    with pytest.raises(ValueError, match="unknown roles"):
        parse_project_policy_yaml(
            """schema_version: 1
roles:
  operator:
    capabilities: []
""",
            known_role_keys={"developer"},
        )
