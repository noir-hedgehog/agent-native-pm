from __future__ import annotations

import json
import time
import urllib.request
from typing import Any, Dict, Optional, Protocol


class PlaneTransport(Protocol):
    def post_comment(self, task_id: str, body: str) -> Dict[str, Any]:
        ...

    def patch_task(self, task_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        ...


class HttpPlaneTransport:
    def __init__(self, base_url: str, token: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _request(self, method: str, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
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

    def post_comment(self, task_id: str, body: str) -> Dict[str, Any]:
        return self._request("POST", f"/plane/tasks/{task_id}/comments", {"body": body})

    def patch_task(self, task_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._request("PATCH", f"/plane/tasks/{task_id}", payload)


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
    ) -> Dict[str, Any]:
        body = (
            f"[Stage Started] role={stage_role} agent={agent_profile} started_at={started_at}"
            f" session={task_session_id or '-'} run={agent_run_id or '-'}"
        )
        return self._retry_post_comment(task_id, body)

    def post_stage_progress(
        self,
        *,
        task_id: str,
        stage_role: str,
        summary: str,
        evidence: Optional[str] = None,
        task_session_id: Optional[str] = None,
        agent_run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        evidence_part = evidence or "n/a"
        body = (
            f"[Stage Progress] role={stage_role} summary={summary} evidence={evidence_part}"
            f" session={task_session_id or '-'} run={agent_run_id or '-'}"
        )
        return self._retry_post_comment(task_id, body)

    def post_stage_completed(
        self,
        *,
        task_id: str,
        handoff: Dict[str, Any],
        task_session_id: Optional[str] = None,
        agent_run_id: Optional[str] = None,
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
        return self._retry_post_comment(task_id, body)

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
    ) -> Dict[str, Any]:
        body = (
            "[Stage Failed] "
            f"role={stage_role} reason={reason} retries_used={retries_used} escalation={escalation_request}"
            f" session={task_session_id or '-'} run={agent_run_id or '-'}"
        )
        return self._retry_post_comment(task_id, body)

    def update_task_status(self, *, task_id: str, status: str) -> Dict[str, Any]:
        return self._retry(lambda: self.transport.patch_task(task_id, {"status": status}))

    def _retry_post_comment(self, task_id: str, body: str) -> Dict[str, Any]:
        return self._retry(lambda: self.transport.post_comment(task_id, body))

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
