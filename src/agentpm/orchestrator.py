from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Protocol

from .agent_accounts import AgentAccountRegistry
from .approval import ApprovalService
from .pipeline import SerialPipelineExecutor
from .store import AuditEvent, Store
from .webhook import handle_assignment_webhook, normalize_assignment_event


class AgentAdapter(Protocol):
    def start_run(self, payload: Dict[str, Any]) -> Any:
        ...

    def stream_events(self, provider_run_id: str) -> list[Dict[str, Any]]:
        ...


class PlaneAdapter(Protocol):
    def post_stage_started(self, **kwargs) -> Dict[str, Any]:
        ...

    def post_stage_progress(self, **kwargs) -> Dict[str, Any]:
        ...

    def post_stage_completed(self, **kwargs) -> Dict[str, Any]:
        ...

    def post_stage_failed(self, **kwargs) -> Dict[str, Any]:
        ...

    def update_task_status(self, *, task_id: str, status: str, **kwargs) -> Dict[str, Any]:
        ...


class AssignmentOrchestrator:
    def __init__(self, store: Store, agent_adapter: AgentAdapter, plane_adapter: PlaneAdapter, secret: str) -> None:
        self.store = store
        self.agent_adapter = agent_adapter
        self.plane_adapter = plane_adapter
        self.secret = secret
        self.agent_registry = AgentAccountRegistry.from_env()

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def process_assignment(self, *, raw_body: bytes, headers: Mapping[str, str]) -> Dict[str, Any]:
        receipt, payload, event = self.accept_assignment(raw_body=raw_body, headers=headers)
        if payload is None or event is None:
            return receipt
        return self.process_accepted_assignment(receipt=receipt, payload=payload, event=event)

    def accept_assignment(
        self, *, raw_body: bytes, headers: Mapping[str, str]
    ) -> tuple[Dict[str, Any], Dict[str, Any] | None, Dict[str, Any] | None]:
        status, response = handle_assignment_webhook(
            raw_body=raw_body,
            headers=headers,
            secret=self.secret,
            store=self.store,
        )
        if status != 202:
            raise RuntimeError(f"unexpected webhook handler status: {status}")

        if response.get("ignored"):
            return ({
                "accepted": False,
                "ignored": True,
                "reason": response.get("reason"),
                "task_session_id": None,
                "agent_run_id": None,
            }, None, None)

        if response["duplicate"]:
            return ({
                "accepted": True,
                "duplicate": True,
                "task_session_id": response["task_session_id"],
                "agent_run_id": None,
            }, None, None)

        payload = json.loads(raw_body.decode("utf-8"))
        event = normalize_assignment_event(payload)
        receipt = {
            "accepted": True,
            "duplicate": False,
            "task_session_id": response["task_session_id"],
            "agent_run_id": None,
        }
        return receipt, payload, event

    def process_accepted_assignment(
        self, *, receipt: Dict[str, Any], payload: Dict[str, Any], event: Dict[str, Any]
    ) -> Dict[str, Any]:
        response = receipt
        task = payload.get("task") or payload.get("data") or {}
        assignee_id = event.get("assignee_id") or "agent_openclaw_default"
        agent_account = self.agent_registry.resolve_assignee(str(assignee_id))
        agent_profile = agent_account.agent_id if agent_account else str(assignee_id)

        project_policy = self.store.get_latest_project_policy(event["project_id"])
        self.store.add_audit_event(
            AuditEvent(
                event_type="assignment.execution_context",
                task_id=event["task_id"],
                task_session_id=response["task_session_id"],
                payload={
                    "task": task,
                    "event": event,
                    "policy_version": project_policy.version if project_policy else None,
                },
                occurred_at=self._now_iso(),
            )
        )
        if project_policy:
            pipeline_result = SerialPipelineExecutor(
                store=self.store,
                agent_adapter=self.agent_adapter,
                plane_adapter=self.plane_adapter,
            ).execute(
                project_id=event["project_id"],
                task_session_id=response["task_session_id"],
                task_id=event["task_id"],
                task=task,
                pipeline_roles=project_policy.pipeline_definition,
                agent_profile_by_role=project_policy.agent_profile_by_role,
                transition_approval_rules=project_policy.transition_approval_rules,
            )
            agent_run_ids = pipeline_result.get("agent_run_ids") or []
            return {
                "accepted": True,
                "duplicate": False,
                "task_session_id": response["task_session_id"],
                "agent_run_id": agent_run_ids[0] if agent_run_ids else None,
                "agent_run_ids": agent_run_ids,
                "completed": pipeline_result.get("completed", False),
                "awaiting_approval": pipeline_result.get("awaiting_approval", False),
                "approval_id": pipeline_result.get("approval_id"),
                "policy_version": project_policy.version,
            }

        agent_identity_payload = {
            "agent_profile": agent_profile,
            "plane_assignee_id": assignee_id,
        }
        if agent_account:
            agent_identity_payload.update(
                {
                    "plane_user_id": agent_account.plane_user_id,
                    "plane_user_email": agent_account.email,
                }
            )

        run = self.store.create_agent_run(
            task_session_id=response["task_session_id"],
            stage_role="coder",
            agent_provider="openclaw",
            agent_profile=agent_profile,
            status="queued",
        )

        self.store.add_audit_event(
            AuditEvent(
                event_type="agent_run.created",
                task_id=event["task_id"],
                task_session_id=response["task_session_id"],
                payload={"agent_run_id": run.agent_run_id, **agent_identity_payload},
                occurred_at=self._now_iso(),
            )
        )

        self.plane_adapter.post_stage_started(
            task_id=event["task_id"],
            stage_role="coder",
            agent_profile=agent_profile,
            started_at=self._now_iso(),
            task_session_id=response["task_session_id"],
            agent_run_id=run.agent_run_id,
            project_id=event["project_id"],
        )

        start_result = self.agent_adapter.start_run(
            {
                "task_session_id": response["task_session_id"],
                "agent_run_id": run.agent_run_id,
                "task_id": event["task_id"],
                "stage_role": "coder",
                "instruction": (
                    task.get("description")
                    or task.get("description_stripped")
                    or task.get("description_html")
                    or task.get("title")
                    or task.get("name")
                    or "Complete assigned task"
                ),
                "context": {
                    "task_title": task.get("title") or task.get("name"),
                    "task_description": (
                        task.get("description")
                        or task.get("description_stripped")
                        or task.get("description_html")
                    ),
                    "task_key": task.get("key") or task.get("identifier"),
                    "agent_id": agent_profile,
                    "plane_assignee_id": assignee_id,
                },
                "policy": {"max_retry": 1},
            }
        )

        self.store.transition_agent_run(run.agent_run_id, "running")
        self.store.add_audit_event(
            AuditEvent(
                event_type="agent_run.started",
                task_id=event["task_id"],
                task_session_id=response["task_session_id"],
                payload={
                    "agent_run_id": run.agent_run_id,
                    "provider_run_id": start_result.provider_run_id,
                    "provider_session_id": start_result.provider_session_id,
                },
                occurred_at=self._now_iso(),
            )
        )

        events = self.agent_adapter.stream_events(start_result.provider_run_id)
        completed = False

        for stream_event in events:
            stream_type = stream_event.get("type")
            payload_data = stream_event.get("payload", {})

            if stream_type in {"run.output", "run.progress"}:
                summary = payload_data.get("content") or payload_data.get("summary") or "in progress"
                self.plane_adapter.post_stage_progress(
                    task_id=event["task_id"],
                    stage_role="coder",
                    summary=summary,
                    evidence=None,
                    task_session_id=response["task_session_id"],
                    agent_run_id=run.agent_run_id,
                    project_id=event["project_id"],
                )

            if stream_type == "run.completed":
                handoff = payload_data.get("handoff_hint", {})
                handoff_goal = handoff.get("goal") or "complete assigned coding task"
                handoff_completed = handoff.get("completed") or []
                handoff_evidence = handoff.get("evidence") or []
                handoff_risks = handoff.get("risks") or []
                handoff_next = handoff.get("next_actions") or []
                handoff_confidence = handoff.get("confidence") or "medium"

                self.store.save_handoff_contract(
                    agent_run_id=run.agent_run_id,
                    goal=handoff_goal,
                    completed=handoff_completed,
                    evidence=handoff_evidence,
                    risks=handoff_risks,
                    next_actions=handoff_next,
                    confidence=handoff_confidence,
                )
                self.store.transition_agent_run(run.agent_run_id, "succeeded")
                self.store.update_task_session_status(response["task_session_id"], "awaiting_review")
                self.plane_adapter.post_stage_completed(
                    task_id=event["task_id"],
                    handoff={
                        "goal": handoff_goal,
                        "completed": handoff_completed,
                        "evidence": handoff_evidence,
                        "risks": handoff_risks,
                        "next_actions": handoff_next,
                        "confidence": handoff_confidence,
                    },
                    task_session_id=response["task_session_id"],
                    agent_run_id=run.agent_run_id,
                    project_id=event["project_id"],
                )
                self.plane_adapter.update_task_status(
                    task_id=event["task_id"],
                    status="awaiting_review",
                    project_id=event["project_id"],
                )
                self.store.add_audit_event(
                    AuditEvent(
                        event_type="agent_run.completed",
                        task_id=event["task_id"],
                        task_session_id=response["task_session_id"],
                        payload={"agent_run_id": run.agent_run_id},
                        occurred_at=self._now_iso(),
                    )
                )
                completed = True

            if stream_type == "run.failed":
                reason = payload_data.get("error", "agent run failed")
                self.store.transition_agent_run(run.agent_run_id, "failed")
                self.store.update_task_session_status(response["task_session_id"], "failed")
                self.plane_adapter.post_stage_failed(
                    task_id=event["task_id"],
                    stage_role="coder",
                    reason=reason,
                    retries_used=0,
                    escalation_request="manual intervention required",
                    task_session_id=response["task_session_id"],
                    agent_run_id=run.agent_run_id,
                    project_id=event["project_id"],
                )
                self.plane_adapter.update_task_status(
                    task_id=event["task_id"],
                    status="failed",
                    project_id=event["project_id"],
                )
                self.store.add_audit_event(
                    AuditEvent(
                        event_type="agent_run.failed",
                        task_id=event["task_id"],
                        task_session_id=response["task_session_id"],
                        payload={"agent_run_id": run.agent_run_id, "reason": reason},
                        occurred_at=self._now_iso(),
                    )
                )

        return {
            "accepted": True,
            "duplicate": False,
            "task_session_id": response["task_session_id"],
            "agent_run_id": run.agent_run_id,
            "completed": completed,
        }

    def record_transition_decision(
        self, *, approval_id: str, decision: str, reviewer_id: str, note: str | None = None
    ) -> Dict[str, Any]:
        approval = self.store.get_transition_approval(approval_id)
        if approval is None:
            raise KeyError(f"unknown approval_id: {approval_id}")
        if approval.status != "pending":
            raise ValueError(f"approval is already {approval.status}")
        session = self.store.get_task_session(approval.task_session_id)
        if session is None:
            raise KeyError(f"unknown task_session_id: {approval.task_session_id}")

        service = ApprovalService(self.store)
        if decision == "approve":
            resolved = service.approve(
                task_id=session.task_id,
                approval_id=approval_id,
                reviewer_id=reviewer_id,
                note=note,
            )
            self.store.update_task_session_status(session.task_session_id, "in_progress")
            return {"approval": resolved.__dict__, "resume_queued": True}
        if decision == "reject":
            if not note:
                raise ValueError("rejection note is required")
            resolved = service.reject(
                task_id=session.task_id,
                approval_id=approval_id,
                reviewer_id=reviewer_id,
                note=note,
            )
            self.store.update_task_session_status(session.task_session_id, "blocked")
            self.plane_adapter.update_task_status(
                task_id=session.task_id,
                status="failed",
                project_id=session.project_id,
            )
            return {"approval": resolved.__dict__, "resume_queued": False, "session_status": "blocked"}
        raise ValueError("decision must be approve or reject")

    def resume_approved_transition(self, approval_id: str) -> Dict[str, Any]:
        approval = self.store.get_transition_approval(approval_id)
        if approval is None:
            raise KeyError(f"unknown approval_id: {approval_id}")
        if approval.status != "approved":
            raise ValueError(f"approval must be approved before resume, got {approval.status}")
        session = self.store.get_task_session(approval.task_session_id)
        if session is None:
            raise KeyError(f"unknown task_session_id: {approval.task_session_id}")

        context_events = [
            item
            for item in self.store.list_audit_events_for_task(session.task_id)
            if item.task_session_id == session.task_session_id and item.event_type == "assignment.execution_context"
        ]
        if not context_events:
            raise RuntimeError("assignment execution context is missing; cannot safely resume")
        context = context_events[-1].payload
        policy_version = context.get("policy_version")
        policies = self.store.list_project_policy_versions(session.project_id)
        policy = next((item for item in policies if item.version == policy_version), None)
        if policy is None:
            raise RuntimeError(f"project policy version {policy_version} is unavailable")

        if approval.to_stage_role == "done":
            self.store.update_task_session_status(session.task_session_id, "done")
            self.plane_adapter.update_task_status(
                task_id=session.task_id,
                status="done",
                project_id=session.project_id,
            )
            return {"completed": True, "task_session_id": session.task_session_id, "agent_run_ids": []}

        try:
            start_index = policy.pipeline_definition.index(approval.to_stage_role)
        except ValueError as exc:
            raise RuntimeError(
                f"approval target role {approval.to_stage_role} is not in policy version {policy.version}"
            ) from exc
        previous = self.store.get_handoff_contract(approval.from_run_id)
        previous_payload = (
            {
                "goal": previous.goal,
                "completed": previous.completed,
                "evidence": previous.evidence,
                "risks": previous.risks,
                "next_actions": previous.next_actions,
                "confidence": previous.confidence,
            }
            if previous
            else None
        )
        existing_runs = [run.agent_run_id for run in self.store.list_agent_runs_for_session(session.task_session_id)]
        return SerialPipelineExecutor(
            store=self.store,
            agent_adapter=self.agent_adapter,
            plane_adapter=self.plane_adapter,
        ).execute(
            project_id=session.project_id,
            task_session_id=session.task_session_id,
            task_id=session.task_id,
            task=context.get("task") or {},
            pipeline_roles=policy.pipeline_definition,
            agent_profile_by_role=policy.agent_profile_by_role,
            transition_approval_rules=policy.transition_approval_rules,
            start_index=start_index,
            previous_handoff=previous_payload,
            existing_run_ids=existing_runs,
        )
