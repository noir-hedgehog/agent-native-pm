# Copyright (c) 2026-present Mesh contributors
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from plane.db.models import (
    AgentExecutionProfile,
    IssueComment,
    MeshAuditEvent,
    MeshRunAttempt,
    MeshStageRun,
)
from plane.mesh.discovery import leave_stage_unassigned
from plane.mesh.runtime import resume_wait


@shared_task(queue="mesh-runner")
def resume_mesh_wait(stage_run_id: str, wait_node_id: str):
    run = resume_wait(stage_run_id=stage_run_id, wait_node_id=wait_node_id)
    return {"status": run.status, "run_id": str(run.id), "current_node_id": run.current_node_id}


@shared_task(queue="mesh-runner", bind=True, max_retries=2, default_retry_delay=30)
def start_mesh_stage(self, stage_run_id: str):
    """Start an explicitly assigned Mesh stage through its Agent endpoint."""
    try:
        stage, attempt = _prepare_attempt(stage_run_id)
    except MeshStageRun.DoesNotExist:
        return {"status": "missing", "stage_run_id": stage_run_id}

    if attempt is None:
        return {"status": "waiting_for_assignee", "stage_run_id": stage_run_id}

    try:
        response = _send_agent_task(stage, attempt)
    except (OSError, ValueError, urllib.error.URLError) as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        _record_start_failure(stage_run_id, attempt.id, str(exc))
        return {"status": "waiting_for_assignee", "error": str(exc)}

    attempt.provider_run_id = str(response.get("id") or response.get("task_id") or "")
    attempt.provider_session_id = str(response.get("contextId") or response.get("session_id") or "")
    attempt.status = MeshRunAttempt.Status.RUNNING
    attempt.save(update_fields=["provider_run_id", "provider_session_id", "status", "updated_at"])
    return {"status": "running", "attempt_id": str(attempt.id), "provider_run_id": attempt.provider_run_id}


@transaction.atomic
def _prepare_attempt(stage_run_id: str):
    stage = (
        MeshStageRun.objects.select_for_update()
        .select_related("assigned_agent__user", "loop_run__work_item", "functional_role")
        .get(id=stage_run_id, deleted_at__isnull=True)
    )
    if not stage.assigned_agent_id:
        leave_stage_unassigned(stage)
        return stage, None

    agent = stage.assigned_agent
    if agent.status != agent.Status.ACTIVE or not (agent.agent_card or {}).get("available", True):
        leave_stage_unassigned(stage)
        _notify_pm(stage, "The selected Agent is unavailable. The work item has returned to Unassigned.")
        return stage, None

    execution_profile = (
        AgentExecutionProfile.objects.filter(agent=agent, is_active=True, deleted_at__isnull=True)
        .order_by("-is_default", "-configuration_version")
        .first()
    )
    provider = execution_profile.provider if execution_profile else agent.runtime_provider
    model = execution_profile.model if execution_profile else "unspecified"
    attempt = MeshRunAttempt.objects.create(
        workspace_id=stage.workspace_id,
        project_id=stage.project_id,
        stage_run=stage,
        agent=agent,
        execution_profile=execution_profile,
        provider=provider,
        model=model,
        configuration_version=execution_profile.configuration_version if execution_profile else 1,
        status=MeshRunAttempt.Status.QUEUED,
    )
    stage.status = MeshStageRun.Status.RUNNING
    stage.started_at = stage.started_at or timezone.now()
    stage.save(update_fields=["status", "started_at", "updated_at"])
    return stage, attempt


def _send_agent_task(stage: MeshStageRun, attempt: MeshRunAttempt) -> dict:
    endpoint = (stage.assigned_agent.endpoint_url or "").strip()
    if not endpoint:
        raise ValueError("Assigned Agent has no endpoint_url")
    message = {
        "jsonrpc": "2.0",
        "id": str(attempt.id),
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [
                    {
                        "kind": "text",
                        "text": stage.objective or f"Work on {stage.loop_run.work_item.name}",
                    }
                ],
                "messageId": str(attempt.id),
            },
            "metadata": {
                "mesh_run_id": str(stage.loop_run_id),
                "mesh_stage_run_id": str(stage.id),
                "work_item_id": str(stage.loop_run.work_item_id),
                "project_id": str(stage.project_id),
                "required_evidence": stage.required_evidence,
            },
        },
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(message).encode("utf-8"),
        headers={"Content-Type": "application/json", **_auth_headers(attempt.execution_profile)},
        method="POST",
    )
    timeout = int(os.environ.get("MESH_AGENT_START_TIMEOUT_SECONDS", "30"))
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Agent endpoint returned a non-object response")
    if payload.get("error"):
        raise ValueError(f"Agent endpoint rejected task: {payload['error']}")
    return payload.get("result") if isinstance(payload.get("result"), dict) else payload


def _auth_headers(execution_profile: AgentExecutionProfile | None) -> dict[str, str]:
    if not execution_profile or not execution_profile.secret_reference:
        return {}
    reference = execution_profile.secret_reference
    if not reference.startswith("env:"):
        return {}
    secret = os.environ.get(reference[4:])
    return {"Authorization": f"Bearer {secret}"} if secret else {}


@transaction.atomic
def _record_start_failure(stage_run_id, attempt_id, message):
    stage = MeshStageRun.objects.select_for_update().select_related("loop_run__work_item").get(id=stage_run_id)
    actor_agent = stage.assigned_agent
    MeshRunAttempt.objects.filter(id=attempt_id).update(
        status=MeshRunAttempt.Status.FAILED,
        completed_at=timezone.now(),
        usage={"start_error": message[:2000]},
    )
    leave_stage_unassigned(stage)
    MeshAuditEvent.objects.create(
        workspace_id=stage.workspace_id,
        project_id=stage.project_id,
        loop_run_id=stage.loop_run_id,
        work_item_id=stage.loop_run.work_item_id,
        actor_agent=actor_agent,
        event_type="stage.start_failed",
        payload={"stage_run_id": str(stage.id), "attempt_id": str(attempt_id), "message": message[:2000]},
        occurred_at=timezone.now(),
    )
    _notify_pm(stage, "Agent startup failed. The work item has returned to Unassigned for PM review.")


def _notify_pm(stage, message: str) -> None:
    IssueComment.objects.create(
        workspace_id=stage.workspace_id,
        project_id=stage.project_id,
        issue_id=stage.loop_run.work_item_id,
        actor=None,
        comment_html=f"<p><strong>Mesh:</strong> {message}</p>",
        external_source="mesh-runner",
        external_id=f"stage:{stage.id}:{stage.status}",
    )
