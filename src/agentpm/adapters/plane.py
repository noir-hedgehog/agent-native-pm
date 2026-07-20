from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request
from typing import Any, Dict, Optional, Protocol


class PlaneTransport(Protocol):
    def post_comment(self, task_id: str, body: str, **context: str | None) -> Dict[str, Any]:
        ...

    def patch_task(self, task_id: str, payload: Dict[str, Any], **context: str | None) -> Dict[str, Any]:
        ...


class HttpPlaneTransport:
    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        *,
        api_key_header: str = "X-Api-Key",
        workspace_slug: str | None = None,
        project_id: str | None = None,
        comment_path_template: str | None = None,
        task_path_template: str | None = None,
        comment_body_field: str = "comment_html",
        status_field: str = "status",
        status_map: Dict[str, str] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.api_key_header = api_key_header
        self.workspace_slug = workspace_slug
        self.project_id = project_id
        self.comment_path_template = comment_path_template or (
            "/api/v1/workspaces/{workspace_slug}/projects/{project_id}/work-items/{task_id}/comments/"
        )
        self.task_path_template = task_path_template or (
            "/api/v1/workspaces/{workspace_slug}/projects/{project_id}/work-items/{task_id}/"
        )
        self.comment_body_field = comment_body_field
        self.status_field = status_field
        self.status_map = status_map or {}

    @classmethod
    def from_env(cls) -> "HttpPlaneTransport":
        status_map_raw = os.environ.get("PLANE_STATUS_MAP", "{}")
        try:
            status_map = json.loads(status_map_raw)
        except json.JSONDecodeError as exc:
            raise ValueError("PLANE_STATUS_MAP must be valid JSON") from exc
        if not isinstance(status_map, dict):
            raise ValueError("PLANE_STATUS_MAP must be a JSON object")

        return cls(
            base_url=_required_env("PLANE_API_BASE_URL"),
            token=os.environ.get("PLANE_API_TOKEN"),
            api_key_header=os.environ.get("PLANE_API_KEY_HEADER", "X-Api-Key"),
            workspace_slug=os.environ.get("PLANE_WORKSPACE_SLUG"),
            project_id=os.environ.get("PLANE_PROJECT_ID"),
            comment_path_template=os.environ.get("PLANE_COMMENT_PATH_TEMPLATE"),
            task_path_template=os.environ.get("PLANE_TASK_PATH_TEMPLATE"),
            comment_body_field=os.environ.get("PLANE_COMMENT_BODY_FIELD", "comment_html"),
            status_field=os.environ.get("PLANE_STATUS_FIELD", "status"),
            status_map={str(key): str(value) for key, value in status_map.items()},
        )

    def _request(self, method: str, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers[self.api_key_header] = self.token
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url=f"{self.base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        with urllib.request.urlopen(req) as response:  # nosec B310
            data = response.read().decode("utf-8")
            return json.loads(data) if data else {}

    def post_comment(self, task_id: str, body: str, **context: str | None) -> Dict[str, Any]:
        path = self._format_path(self.comment_path_template, task_id=task_id, context=context)
        correlation_id = context.get("agent_run_id") or context.get("task_session_id") or task_id
        body_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
        payload = {
            self.comment_body_field: body,
            "external_source": "agentpm",
            "external_id": f"{correlation_id}:{body_hash}",
        }
        return self._request("POST", path, payload)

    def patch_task(self, task_id: str, payload: Dict[str, Any], **context: str | None) -> Dict[str, Any]:
        path = self._format_path(self.task_path_template, task_id=task_id, context=context)
        mapped_payload = {}
        for key, value in payload.items():
            if key == "status":
                mapped_payload[self.status_field] = self.status_map.get(str(value), value)
            else:
                mapped_payload[key] = value
        return self._request("PATCH", path, mapped_payload)

    def _format_path(self, template: str, *, task_id: str, context: Dict[str, str | None]) -> str:
        workspace_slug = context.get("workspace_slug") or self.workspace_slug
        project_id = context.get("project_id") or self.project_id
        values = {
            "workspace_slug": workspace_slug,
            "project_id": project_id,
            "task_id": task_id,
            "issue_id": task_id,
        }
        missing = [key for key, value in values.items() if value is None and f"{{{key}}}" in template]
        if missing:
            raise ValueError(f"missing Plane path values: {', '.join(missing)}")
        return template.format(**values)


class PlaneWritebackAdapter:
    def __init__(self, transport: PlaneTransport, max_attempts: int = 3, retry_delay_seconds: float = 0.05) -> None:
        self.transport = transport
        self.max_attempts = max_attempts
        self.retry_delay_seconds = retry_delay_seconds

    def post_stage_started(
        self,
        *,
        task_id: str,
        stage_role: str,
        agent_profile: str,
        started_at: str,
        task_session_id: Optional[str] = None,
        agent_run_id: Optional[str] = None,
        project_id: Optional[str] = None,
        workspace_slug: Optional[str] = None,
    ) -> Dict[str, Any]:
        body = (
            f"[Stage Started] role={stage_role} agent={agent_profile} started_at={started_at}"
            f" session={task_session_id or '-'} run={agent_run_id or '-'}"
        )
        return self._retry_post_comment(
            task_id,
            body,
            task_session_id=task_session_id,
            agent_run_id=agent_run_id,
            project_id=project_id,
            workspace_slug=workspace_slug,
        )

    def post_stage_progress(
        self,
        *,
        task_id: str,
        stage_role: str,
        summary: str,
        evidence: Optional[str] = None,
        task_session_id: Optional[str] = None,
        agent_run_id: Optional[str] = None,
        project_id: Optional[str] = None,
        workspace_slug: Optional[str] = None,
    ) -> Dict[str, Any]:
        evidence_part = evidence or "n/a"
        body = (
            f"[Stage Progress] role={stage_role} summary={summary} evidence={evidence_part}"
            f" session={task_session_id or '-'} run={agent_run_id or '-'}"
        )
        return self._retry_post_comment(
            task_id,
            body,
            task_session_id=task_session_id,
            agent_run_id=agent_run_id,
            project_id=project_id,
            workspace_slug=workspace_slug,
        )

    def post_stage_completed(
        self,
        *,
        task_id: str,
        handoff: Dict[str, Any],
        task_session_id: Optional[str] = None,
        agent_run_id: Optional[str] = None,
        project_id: Optional[str] = None,
        workspace_slug: Optional[str] = None,
    ) -> Dict[str, Any]:
        completed = "; ".join(handoff.get("completed", [])) if isinstance(handoff.get("completed"), list) else handoff.get("completed", "")
        evidence = "; ".join(handoff.get("evidence", [])) if isinstance(handoff.get("evidence"), list) else handoff.get("evidence", "")
        risks = "; ".join(handoff.get("risks", [])) if isinstance(handoff.get("risks"), list) else handoff.get("risks", "")
        next_actions = "; ".join(handoff.get("next_actions", [])) if isinstance(handoff.get("next_actions"), list) else handoff.get("next_actions", "")

        body = (
            "[Stage Completed]\n"
            f"Goal: {handoff.get('goal', '')}\n"
            f"Completed: {completed}\n"
            f"Evidence: {evidence}\n"
            f"Risks: {risks}\n"
            f"Next: {next_actions}\n"
            f"Confidence: {handoff.get('confidence', 'unknown')}\n"
            f"Session: {task_session_id or '-'}\n"
            f"Run: {agent_run_id or '-'}"
        )
        return self._retry_post_comment(
            task_id,
            body,
            task_session_id=task_session_id,
            agent_run_id=agent_run_id,
            project_id=project_id,
            workspace_slug=workspace_slug,
        )

    def post_stage_failed(
        self,
        *,
        task_id: str,
        stage_role: str,
        reason: str,
        retries_used: int,
        escalation_request: str,
        task_session_id: Optional[str] = None,
        agent_run_id: Optional[str] = None,
        project_id: Optional[str] = None,
        workspace_slug: Optional[str] = None,
    ) -> Dict[str, Any]:
        body = (
            "[Stage Failed] "
            f"role={stage_role} reason={reason} retries_used={retries_used} escalation={escalation_request}"
            f" session={task_session_id or '-'} run={agent_run_id or '-'}"
        )
        return self._retry_post_comment(
            task_id,
            body,
            task_session_id=task_session_id,
            agent_run_id=agent_run_id,
            project_id=project_id,
            workspace_slug=workspace_slug,
        )

    def update_task_status(
        self,
        *,
        task_id: str,
        status: str,
        project_id: Optional[str] = None,
        workspace_slug: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self._retry(
            lambda: self.transport.patch_task(
                task_id,
                {"status": status},
                project_id=project_id,
                workspace_slug=workspace_slug,
            )
        )

    def _retry_post_comment(self, task_id: str, body: str, **context: str | None) -> Dict[str, Any]:
        return self._retry(lambda: self.transport.post_comment(task_id, body, **context))

    def _retry(self, operation):
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                return operation()
            except Exception as exc:
                last_error = exc
                if attempt == self.max_attempts:
                    raise
                time.sleep(self.retry_delay_seconds)
        if last_error is not None:
            raise last_error
        raise RuntimeError("retry operation failed with unknown error")


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ValueError(f"{name} is required")
    return value
