# Copyright (c) 2026-present Mesh contributors
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from django.db import transaction
from django.conf import settings
from django.utils import timezone

from plane.db.models import (
    AgentProfile,
    IssueAssignee,
    MeshApproval,
    MeshAuditEvent,
    MeshFunctionalRole,
    MeshLoopRun,
    MeshRunAttempt,
    MeshStageRun,
    User,
)


@transaction.atomic
def complete_stage(
    *,
    stage_run_id: str,
    actor_agent: AgentProfile,
    outcome: str,
    evidence: list,
    selected_next_node_id: str | None = None,
) -> MeshLoopRun:
    stage = (
        MeshStageRun.objects.select_for_update()
        .select_related("loop_run__definition", "loop_run__work_item", "assigned_agent")
        .get(id=stage_run_id, deleted_at__isnull=True)
    )
    if stage.assigned_agent_id != actor_agent.id:
        raise ValueError("Only the Agent assigned to this Stage can complete it")
    if stage.status not in {MeshStageRun.Status.QUEUED, MeshStageRun.Status.RUNNING}:
        raise ValueError(f"Stage cannot be completed from status {stage.status}")
    if outcome not in {"succeeded", "failed"}:
        raise ValueError("outcome must be succeeded or failed")
    attempt = stage.attempts.filter(deleted_at__isnull=True).order_by("-created_at").first()
    now = timezone.now()
    if attempt:
        attempt.status = MeshRunAttempt.Status.SUCCEEDED if outcome == "succeeded" else MeshRunAttempt.Status.FAILED
        attempt.evidence = evidence
        attempt.completed_at = now
        attempt.save(update_fields=["status", "evidence", "completed_at", "updated_at"])
    if outcome == "failed":
        stage.status = MeshStageRun.Status.FAILED
        stage.completed_at = now
        stage.save(update_fields=["status", "completed_at", "updated_at"])
        MeshLoopRun.objects.filter(id=stage.loop_run_id).update(status=MeshLoopRun.Status.FAILED)
        _audit(stage, actor_agent=actor_agent, event_type="stage.failed", payload={"evidence": evidence})
        stage.loop_run.refresh_from_db()
        return stage.loop_run

    stage.status = MeshStageRun.Status.SUCCEEDED
    stage.completed_at = now
    stage.save(update_fields=["status", "completed_at", "updated_at"])
    _audit(stage, actor_agent=actor_agent, event_type="stage.succeeded", payload={"evidence": evidence})
    return _advance_from_node(stage=stage, node_id=stage.node_id, selected_next_node_id=selected_next_node_id)


@transaction.atomic
def resolve_approval(*, approval: MeshApproval, reviewer: User, approved: bool, decision_note: str) -> MeshLoopRun:
    approval = (
        MeshApproval.objects.select_for_update()
        .select_related("loop_run__definition", "loop_run__work_item", "stage_run")
        .get(id=approval.id)
    )
    if approval.status != MeshApproval.Status.PENDING:
        raise ValueError("Approval has already been resolved")
    approval.status = MeshApproval.Status.APPROVED if approved else MeshApproval.Status.REJECTED
    approval.reviewer = reviewer
    approval.decision_note = decision_note
    approval.resolved_at = timezone.now()
    approval.save(update_fields=["status", "reviewer", "decision_note", "resolved_at", "updated_at"])
    if not approved:
        MeshStageRun.objects.filter(id=approval.stage_run_id).update(status=MeshStageRun.Status.FAILED)
        MeshLoopRun.objects.filter(id=approval.loop_run_id).update(status=MeshLoopRun.Status.FAILED)
        approval.loop_run.refresh_from_db()
        return approval.loop_run
    approval.stage_run.status = MeshStageRun.Status.SUCCEEDED
    approval.stage_run.save(update_fields=["status", "updated_at"])
    return _advance_from_node(stage=approval.stage_run, node_id=_approval_node_id(approval))


def _advance_from_node(*, stage: MeshStageRun, node_id: str, selected_next_node_id: str | None = None) -> MeshLoopRun:
    run = MeshLoopRun.objects.select_for_update().select_related("definition", "work_item").get(id=stage.loop_run_id)
    graph = run.definition.graph
    nodes = {str(node.get("id")): node for node in graph.get("nodes") or []}
    adjacency: dict[str, list[str]] = {}
    for edge in graph.get("edges") or []:
        adjacency.setdefault(str(edge.get("from")), []).append(str(edge.get("to")))
    current = node_id
    visited = set()
    while True:
        targets = adjacency.get(current, [])
        if len(targets) > 1:
            if not selected_next_node_id or selected_next_node_id not in targets:
                raise ValueError(f"Node {current} requires selected_next_node_id from: {', '.join(targets)}")
            targets = [selected_next_node_id]
            selected_next_node_id = None
        if not targets:
            raise ValueError(f"Loop node {current} has no outgoing transition")
        current = targets[0]
        if not _record_transition(run):
            IssueAssignee.objects.filter(issue_id=run.work_item_id, deleted_at__isnull=True).delete()
            MeshAuditEvent.objects.create(
                workspace_id=run.workspace_id,
                project_id=run.project_id,
                loop_run=run,
                work_item_id=run.work_item_id,
                event_type="loop.transition_limit_exceeded",
                payload={"max_transitions": (graph.get("limits") or {}).get("max_transitions")},
                occurred_at=timezone.now(),
            )
            return run
        if current in visited:
            raise ValueError("Loop transition revisited a node before reaching a runnable boundary")
        visited.add(current)
        node = nodes[current]
        node_type = node.get("type")
        run.current_node_id = current
        if node_type == "complete":
            run.status = MeshLoopRun.Status.COMPLETED
            run.completed_at = timezone.now()
            run.save(update_fields=["current_node_id", "status", "budget", "completed_at", "updated_at"])
            IssueAssignee.objects.filter(issue_id=run.work_item_id, deleted_at__isnull=True).delete()
            return run
        if node_type == "approval":
            stage.status = MeshStageRun.Status.AWAITING_APPROVAL
            stage.save(update_fields=["status", "updated_at"])
            MeshApproval.objects.get_or_create(
                workspace_id=run.workspace_id,
                project_id=run.project_id,
                loop_run=run,
                stage_run=stage,
                status=MeshApproval.Status.PENDING,
            )
            run.status = MeshLoopRun.Status.AWAITING_APPROVAL
            run.save(update_fields=["current_node_id", "status", "budget", "updated_at"])
            return run
        if node_type == "wait":
            run.status = MeshLoopRun.Status.QUEUED
            run.save(update_fields=["current_node_id", "status", "budget", "updated_at"])
            queue_wait_resume_on_commit(
                stage_run_id=str(stage.id),
                wait_node_id=current,
                countdown=max(int(node.get("duration_seconds") or 0), 0),
            )
            return run
        if node_type == "stage":
            role_keys = list(node.get("roles") or [])
            role = MeshFunctionalRole.objects.filter(
                project_id=run.project_id,
                key=role_keys[0] if len(role_keys) == 1 else None,
                deleted_at__isnull=True,
            ).first()
            MeshStageRun.objects.create(
                workspace_id=run.workspace_id,
                project_id=run.project_id,
                loop_run=run,
                node_id=current,
                objective=str(node.get("objective") or ""),
                functional_role=role,
                required_evidence=list(node.get("evidence") or []),
            )
            IssueAssignee.objects.filter(issue_id=run.work_item_id, deleted_at__isnull=True).delete()
            run.status = MeshLoopRun.Status.WAITING_FOR_ASSIGNEE
            run.save(update_fields=["current_node_id", "status", "budget", "updated_at"])
            return run


@transaction.atomic
def resume_wait(*, stage_run_id: str, wait_node_id: str) -> MeshLoopRun:
    stage = (
        MeshStageRun.objects.select_for_update()
        .select_related("loop_run__definition", "loop_run__work_item")
        .get(id=stage_run_id, deleted_at__isnull=True)
    )
    run = MeshLoopRun.objects.select_for_update().get(id=stage.loop_run_id)
    if run.status != MeshLoopRun.Status.QUEUED or run.current_node_id != wait_node_id:
        return run
    return _advance_from_node(stage=stage, node_id=wait_node_id)


def _record_transition(run: MeshLoopRun) -> bool:
    budget = dict(run.budget or {})
    count = int(budget.get("_mesh_transition_count") or 0) + 1
    budget["_mesh_transition_count"] = count
    run.budget = budget
    maximum = (run.definition.graph.get("limits") or {}).get("max_transitions")
    if isinstance(maximum, int) and count > maximum:
        run.status = MeshLoopRun.Status.FAILED
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "budget", "completed_at", "updated_at"])
        return False
    return True


def _approval_node_id(approval: MeshApproval) -> str:
    run = approval.loop_run
    graph = run.definition.graph
    outgoing = [
        str(edge.get("to")) for edge in graph.get("edges") or [] if str(edge.get("from")) == approval.stage_run.node_id
    ]
    nodes = {str(node.get("id")): node for node in graph.get("nodes") or []}
    return next(
        (node_id for node_id in outgoing if nodes.get(node_id, {}).get("type") == "approval"), run.current_node_id
    )


def _audit(stage, *, actor_agent, event_type, payload):
    MeshAuditEvent.objects.create(
        workspace_id=stage.workspace_id,
        project_id=stage.project_id,
        loop_run_id=stage.loop_run_id,
        work_item_id=stage.loop_run.work_item_id,
        actor_user_id=actor_agent.user_id,
        actor_agent=actor_agent,
        event_type=event_type,
        payload={"stage_run_id": str(stage.id), **payload},
        occurred_at=timezone.now(),
    )


def queue_stage_start_on_commit(stage_run_id: str) -> None:
    if not getattr(settings, "MESH_RUNNER_AUTOSTART", True):
        return
    from plane.bgtasks.mesh_runner import start_mesh_stage

    transaction.on_commit(lambda: start_mesh_stage.delay(stage_run_id))


def queue_wait_resume_on_commit(*, stage_run_id: str, wait_node_id: str, countdown: int) -> None:
    if not getattr(settings, "MESH_RUNNER_AUTOSTART", True):
        return
    from plane.bgtasks.mesh_runner import resume_mesh_wait

    transaction.on_commit(lambda: resume_mesh_wait.apply_async(args=[stage_run_id, wait_node_id], countdown=countdown))
