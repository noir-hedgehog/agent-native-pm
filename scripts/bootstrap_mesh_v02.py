#!/usr/bin/env python3
"""Idempotently prepare the Mesh Platform v0.2 production milestone."""

from __future__ import annotations

import json
import os
from datetime import timedelta

import yaml
from django.db import transaction
from django.utils import timezone

from plane.db.models import (
    AgentExecutionProfile,
    AgentProfile,
    Cycle,
    CycleIssue,
    Issue,
    IssueComment,
    MeshFunctionalRole,
    MeshLoopDefinition,
    MeshProjectMemberRole,
    Project,
    ProjectMember,
    State,
    StateGroup,
)
from plane.mesh.agent_cards import sync_agent_card
from plane.mesh.source_formats import parse_loop_yaml, sha256_text


PROJECT_IDENTIFIER = os.environ.get("MESH_V02_PROJECT_IDENTIFIER", "AGPM")
GATEWAY_BASE_URL = os.environ.get("MESH_V02_GATEWAY_BASE_URL", "").rstrip("/")
SYNC_AGENT_CARDS = os.environ.get("MESH_V02_SYNC_AGENT_CARDS", "0") == "1"

ROLE_ASSIGNMENTS = {
    "hekate": ("pm", "reviewer"),
    "iris": ("developer",),
    "lingxi": ("tester",),
    "taichi": ("observer",),
}

ROLE_CAPABILITIES = {
    "pm": ["work.read", "work.assign", "loop.draft", "handoff.select"],
    "developer": ["work.read", "work.update", "code.write", "test.run"],
    "tester": ["work.read", "work.comment", "test.run", "handoff.reject"],
    "reviewer": ["work.read", "work.comment", "review.approve"],
    "observer": ["work.read", "work.comment"],
}

WORK_ITEMS = (
    ("mesh-v02-a2a-gateway", "A2A Gateway", "Implement and operate the local A2A 1.0 Gateway with per-Agent Cards, bearer authentication, SQLite recovery, idempotency, and isolated worktrees."),
    ("mesh-v02-agent-runtime-profile", "Agent Runtime Profile", "Manage Agent identity metadata, endpoint, Card availability, capabilities, boundaries, execution provider/model, configuration version, workspace mapping, and secret references."),
    ("mesh-v02-runner-lifecycle", "Runner Lifecycle", "Dispatch non-blocking A2A tasks, poll provider state, enforce timeout and retry Policy, and recover failed assignments without changing the Work Item business state."),
    ("mesh-v02-evidence-handoff", "Evidence and Handoff", "Validate strict Evidence, reuse one completion service, preserve explicit handoff selection, and leave unavailable targets Unassigned."),
    ("mesh-v02-console-runtime", "Console Runtime", "Expose Loop start/cancel, Stage assignment, Attempts, Evidence, Handoff, provider/model, and failure details in Mesh Console."),
    ("mesh-v02-e2e-pilot", "E2E Pilot", "Complete the Iris Developer to Lingxi Tester to Hekate Reviewer production Loop and retain the full audit trail."),
    ("mesh-v02-failure-recovery", "Failure Recovery", "Verify omitted handoff, unavailable target, Gateway outage, startup retry, timeout, duplicate poll, and repeated terminal event behavior."),
    ("mesh-v02-release-operations", "Release and Operations", "Back up and restore production, add health and stale-run monitoring, publish mesh-v0.2.0, and freeze the v0.2 data and MCP contracts."),
)

LOOP_SOURCE = """schema_version: 1
name: Mesh code change v1
limits:
  max_transitions: 16
  budget:
    default_max_attempts: 2
nodes:
  - id: assigned
    type: trigger
  - id: develop
    type: stage
    objective: Implement the requested code change in the shared Loop worktree and commit the result.
    roles: [developer]
    required_capabilities: [code.write]
    evidence: [summary, commit, tests, skill_refs, knowledge_refs]
  - id: handoff_to_test
    type: handoff
  - id: test
    type: stage
    objective: Verify the implementation, run relevant tests, and report remaining risks.
    roles: [tester]
    required_capabilities: [test.run]
    evidence: [test_result, risks, skill_refs, knowledge_refs]
  - id: handoff_to_review
    type: handoff
  - id: review
    type: stage
    objective: Review the change, its evidence, and release readiness.
    roles: [reviewer]
    required_capabilities: [review.approve]
    evidence: [review_result, skill_refs, knowledge_refs]
  - id: complete
    type: complete
edges:
  - from: assigned
    to: develop
  - from: develop
    to: handoff_to_test
  - from: handoff_to_test
    to: test
  - from: test
    to: handoff_to_review
  - from: handoff_to_review
    to: review
  - from: review
    to: complete
"""


def _human_admin(project):
    member = (
        ProjectMember.objects.filter(
            project=project,
            role__gte=20,
            is_active=True,
            member__is_bot=False,
            deleted_at__isnull=True,
        )
        .select_related("member")
        .first()
    )
    return member.member if member else project.workspace.owner


def _comment_once(issue, actor, external_id, html):
    comment, created = IssueComment.objects.get_or_create(
        workspace=issue.workspace,
        project=issue.project,
        issue=issue,
        external_source="mesh-v02-bootstrap",
        external_id=external_id,
        defaults={"actor": actor, "comment_html": html, "created_by": actor},
    )
    return created


@transaction.atomic
def bootstrap():
    project = Project.objects.select_related("workspace", "workspace__owner").get(
        identifier=PROJECT_IDENTIFIER,
        deleted_at__isnull=True,
    )
    admin = _human_admin(project)
    project.name = "Mesh Platform"
    project.description = "Mesh Agent-native collaboration platform and production Console."
    project.save(update_fields=["name", "description", "updated_at"])

    superseded, _ = State.all_state_objects.get_or_create(
        workspace=project.workspace,
        project=project,
        name="Superseded",
        defaults={"color": "#8B8D98", "group": StateGroup.CANCELLED.value, "sequence": 56000},
    )
    for sequence_id in (14, 15, 16):
        issue = Issue.issue_objects.filter(project=project, sequence_id=sequence_id).first()
        if not issue:
            continue
        issue.state = superseded
        issue.save(update_fields=["state", "completed_at", "updated_at"])
        _comment_once(
            issue,
            admin,
            f"superseded-agpm-{sequence_id}",
            "<p><strong>Superseded by Mesh v0.2.</strong> This smoke item is retained for audit history; real acceptance now runs through the A2A Loop.</p>",
        )

    now = timezone.now()
    cycle, _ = Cycle.objects.get_or_create(
        workspace=project.workspace,
        project=project,
        external_source="mesh",
        external_id="mesh-v02-real-loop",
        defaults={
            "name": "Mesh v0.2 Real Loop",
            "description": "Production milestone for the first real Developer to Tester to Reviewer Agent Loop.",
            "start_date": now,
            "end_date": now + timedelta(days=21),
            "owned_by": admin,
            "timezone": "Asia/Shanghai",
        },
    )
    cycle.name = "Mesh v0.2 Real Loop"
    cycle.description = "Production milestone for the first real Developer to Tester to Reviewer Agent Loop."
    cycle.owned_by = admin
    cycle.save(update_fields=["name", "description", "owned_by", "updated_at"])

    backlog = State.objects.filter(project=project, group=StateGroup.BACKLOG.value).order_by("sequence").first()
    if not backlog:
        backlog = State.objects.filter(project=project).order_by("sequence").first()
    created_work_items = 0
    for external_id, name, description in WORK_ITEMS:
        issue, created = Issue.objects.get_or_create(
            workspace=project.workspace,
            project=project,
            external_source="mesh",
            external_id=external_id,
            defaults={
                "name": name,
                "description_html": f"<p>{description}</p>",
                "description_stripped": description,
                "priority": "high",
                "state": backlog,
                "created_by": admin,
            },
        )
        issue.name = name
        issue.description_html = f"<p>{description}</p>"
        issue.priority = "high"
        issue.save(update_fields=["name", "description_html", "description_stripped", "priority", "updated_at"])
        CycleIssue.objects.get_or_create(
            workspace=project.workspace,
            project=project,
            cycle=cycle,
            issue=issue,
            defaults={"created_by": admin},
        )
        created_work_items += int(created)

    acceptance, acceptance_created = Issue.objects.get_or_create(
        workspace=project.workspace,
        project=project,
        external_source="mesh",
        external_id="mesh-v02-production-loop-acceptance",
        defaults={
            "name": "Mesh v0.2 Production Loop Acceptance",
            "description_html": "<p>Iris implements, Lingxi tests, and Hekate reviews the first production Mesh Loop.</p>",
            "priority": "urgent",
            "state": backlog,
            "created_by": admin,
        },
    )
    CycleIssue.objects.get_or_create(
        workspace=project.workspace,
        project=project,
        cycle=cycle,
        issue=acceptance,
        defaults={"created_by": admin},
    )

    roles = {}
    for index, (key, capabilities) in enumerate(ROLE_CAPABILITIES.items()):
        role, _ = MeshFunctionalRole.objects.update_or_create(
            workspace=project.workspace,
            project=project,
            key=key,
            deleted_at__isnull=True,
            defaults={
                "name": key.title() if key != "pm" else "PM",
                "capabilities": capabilities,
                "is_default": True,
                "sort_order": index * 1000,
            },
        )
        roles[key] = role

    agent_results = {}
    managed_roles = set(ROLE_CAPABILITIES)
    for agent_id, desired_roles in ROLE_ASSIGNMENTS.items():
        profile = AgentProfile.objects.select_related("user").filter(
            workspace=project.workspace,
            agent_id=agent_id,
            deleted_at__isnull=True,
        ).first()
        if not profile:
            agent_results[agent_id] = "missing_profile"
            continue
        member = ProjectMember.objects.filter(
            project=project,
            member=profile.user,
            is_active=True,
            deleted_at__isnull=True,
        ).first()
        if not member:
            agent_results[agent_id] = "missing_project_membership"
            continue
        MeshProjectMemberRole.objects.filter(
            project=project,
            project_member=member,
            functional_role__key__in=managed_roles,
            deleted_at__isnull=True,
        ).exclude(functional_role__key__in=desired_roles).delete()
        for role_key in desired_roles:
            MeshProjectMemberRole.objects.get_or_create(
                workspace=project.workspace,
                project=project,
                project_member=member,
                functional_role=roles[role_key],
                deleted_at__isnull=True,
                defaults={"assigned_by": admin},
            )
        profile.capability_claims = sorted(
            {capability for role_key in desired_roles for capability in ROLE_CAPABILITIES[role_key]}
        )
        profile.runtime_provider = "openclaw"
        profile.status = AgentProfile.Status.ACTIVE
        if GATEWAY_BASE_URL:
            profile.endpoint_url = f"{GATEWAY_BASE_URL}/agents/{agent_id}/a2a"
            profile.agent_card = {"available": False, "sync_pending": True}
        profile.save(
            update_fields=["capability_claims", "runtime_provider", "status", "endpoint_url", "agent_card", "updated_at"]
        )
        AgentExecutionProfile.objects.update_or_create(
            workspace=project.workspace,
            agent=profile,
            provider="openclaw",
            model="runtime-reported",
            configuration_version=2,
            defaults={
                "secret_reference": "env:MESH_AGENT_GATEWAY_TOKEN",
                "settings": {"workspace_mode": "per_loop", "a2a_protocol_version": "1.0"},
                "is_default": True,
                "is_active": True,
                "created_by": admin,
            },
        )
        if SYNC_AGENT_CARDS:
            try:
                sync_agent_card(profile)
                agent_results[agent_id] = "available"
            except ValueError as exc:
                agent_results[agent_id] = f"unavailable: {exc}"
        else:
            agent_results[agent_id] = "sync_pending"

    graph = parse_loop_yaml(LOOP_SOURCE)
    checksum = sha256_text(LOOP_SOURCE)
    loop = MeshLoopDefinition.objects.filter(
        project=project,
        slug="mesh-code-change-v1",
        checksum=checksum,
        deleted_at__isnull=True,
    ).first()
    loop_created = False
    if not loop:
        latest = MeshLoopDefinition.objects.filter(
            project=project,
            slug="mesh-code-change-v1",
            deleted_at__isnull=True,
        ).order_by("-version").first()
        MeshLoopDefinition.objects.filter(
            project=project,
            slug="mesh-code-change-v1",
            status=MeshLoopDefinition.Status.PUBLISHED,
            deleted_at__isnull=True,
        ).update(status=MeshLoopDefinition.Status.SUPERSEDED)
        loop = MeshLoopDefinition.objects.create(
            workspace=project.workspace,
            project=project,
            slug="mesh-code-change-v1",
            name="Mesh code change v1",
            description="Explicit Developer to Tester to Reviewer production Loop.",
            version=(latest.version + 1 if latest else 1),
            status=MeshLoopDefinition.Status.PUBLISHED,
            source_yaml=LOOP_SOURCE,
            graph=graph,
            checksum=checksum,
            change_note="Mesh v0.2 production acceptance Loop",
            published_by=admin,
            published_at=timezone.now(),
            created_by=admin,
        )
        loop_created = True

    return {
        "project_id": str(project.id),
        "project_name": project.name,
        "project_identifier": project.identifier,
        "cycle_id": str(cycle.id),
        "work_items_created": created_work_items,
        "acceptance_work_item_id": str(acceptance.id),
        "acceptance_work_item_created": acceptance_created,
        "loop_id": str(loop.id),
        "loop_version": loop.version,
        "loop_created": loop_created,
        "agents": agent_results,
    }


print(json.dumps(bootstrap(), ensure_ascii=False, indent=2))
