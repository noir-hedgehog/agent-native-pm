# Agent-Native PM V1 Spec

## 1. Product Definition

### 1.1 One-line definition
A project board system where humans manage goals and approvals, while multiple external agents execute work through orchestrated task handoffs.

### 1.2 Scope (V1)
- Plane is the system of record for tasks and workflow state.
- Agent execution is external (OpenClaw/Codex/Claude side).
- Orchestrator handles assignment-triggered execution, sequencing, approvals, and write-back.
- Multi-agent orchestration is serial pipeline only in V1.

### 1.3 Out of scope (V1)
- No custom PM UI overhaul.
- No multi-entrypoint triggers (email/Slack/buttons).
- No parallel/branching workflow graph.
- No deep control of each agent's internal memory/session implementation.

## 2. Core Concepts

### 2.1 Entities
- Project: policy scope and pipeline config.
- Task: work item in Plane.
- Pipeline: ordered role chain (e.g., `coder -> tester -> reviewer`).
- AgentRun: one execution attempt by one agent profile in a pipeline stage.
- TransitionApproval: optional human gate for stage-to-stage transition.
- HandoffContract: structured handoff generated from natural-language output.

### 2.2 Session model
- One Task can have many AgentRuns.
- Each AgentRun maps to exactly one agent-side session.
- Agent-side session data remains in agent platform.
- Orchestrator stores session references and audit events only.

## 3. User Stories (V1)

1. As a PM, I can assign a task to an agent so execution starts automatically.
2. As a PM, I can define a serial multi-agent pipeline for a project.
3. As a PM, I can require human approval on specific transitions.
4. As a PM, I can see stage-by-stage progress in Plane comments.
5. As a PM, I can read a normalized completion summary regardless of which agent ran.
6. As a tester-role agent, I can reject a previous stage with a required reason.
7. As an operator, I can audit when and why each transition happened.
8. As an operator, I can map task failures to the exact stage and run.
9. As a PM, I can open a new task to start a new session lineage.
10. As a PM, I can track quality metrics like first-pass approval rate.

## 4. Workflow

### 4.1 Trigger
- Primary trigger: task assignment to an agent profile in Plane.
- A unique idempotency key is generated from task + assignment event id.

### 4.2 Execution flow
1. Task assigned to stage-1 agent.
2. Orchestrator creates AgentRun and starts external session.
3. Agent outputs natural language progress and result.
4. Orchestrator extracts `HandoffContract` from agent output.
5. If transition needs approval, create `awaiting_review` gate.
6. On approval, advance to next stage and create next AgentRun.
7. Final stage complete writes final summary and sets task to review/done policy.

### 4.3 Rejection flow
- A stage can reject only the immediately previous stage.
- Rejection requires `reject_reason`.
- Rejection creates a new rerun AgentRun for previous stage.

### 4.4 Failure flow
- Same-agent retry: up to 1 automatic retry.
- Fallback retry: optional alternate agent profile for same role (1 attempt).
- If still failed: task marked `blocked` and human intervention requested.

## 5. Human Approval

### 5.1 Policy model
Approval is configured per transition pair, e.g.:
- `coder -> tester`: no approval
- `tester -> reviewer`: approval required
- `reviewer -> done`: approval required

### 5.2 Timeout policy
- 24h: reminder comment.
- 72h: auto-mark transition as blocked.

## 6. State Machine

### 6.1 Task states
- `todo`
- `in_progress`
- `awaiting_review`
- `done`
- `blocked`
- `failed`

### 6.2 AgentRun states
- `queued`
- `running`
- `succeeded`
- `rejected`
- `failed`
- `canceled`

### 6.3 Transition rules (high level)
- `todo -> in_progress`: first run starts.
- `in_progress -> awaiting_review`: approval-required boundary reached.
- `awaiting_review -> in_progress`: approved and next run starts.
- `in_progress -> done`: final stage succeeded with no final approval required.
- `awaiting_review -> done`: final approval granted.
- `* -> blocked`: policy timeout or unresolved hard failure.
- `* -> failed`: unrecoverable execution failure without fallback.

## 7. Natural Language + Structured Handoff

### 7.1 Principle
- Agent conversations remain natural language.
- Orchestrator generates structured handoff in background.
- If extraction confidence is low, stage is flagged for human check.

### 7.2 HandoffContract schema
- `goal`: what this stage tried to achieve.
- `completed`: what is done.
- `evidence`: links/artifacts/tests/results.
- `risks`: open risks and uncertainty.
- `next_actions`: explicit asks for next stage.
- `confidence`: `low|medium|high`.

## 8. Data Model (Logical)

### 8.1 project_policy
- `id`
- `project_id`
- `pipeline_definition` (ordered roles)
- `transition_approval_rules`
- `transition_timeout_hours`
- `allowed_actions_by_role`

### 8.2 task_session
- `id`
- `project_id`
- `task_id`
- `status`
- `current_stage_index`
- `created_at`
- `updated_at`

### 8.3 agent_run
- `id`
- `task_session_id`
- `stage_role`
- `agent_provider` (`openclaw|codex|claude|...`)
- `agent_profile`
- `provider_session_id`
- `status`
- `retry_index`
- `started_at`
- `ended_at`

### 8.4 handoff_contract
- `id`
- `agent_run_id`
- `goal`
- `completed`
- `evidence`
- `risks`
- `next_actions`
- `confidence`

### 8.5 transition_approval
- `id`
- `task_session_id`
- `from_run_id`
- `to_stage_role`
- `status` (`pending|approved|rejected|timed_out`)
- `reviewer_id`
- `decision_note`
- `created_at`
- `resolved_at`

### 8.6 audit_event
- `id`
- `project_id`
- `task_id`
- `task_session_id`
- `agent_run_id` (nullable)
- `event_type`
- `event_payload`
- `occurred_at`

## 9. Adapter Contracts

### 9.1 Agent Adapter (provider-agnostic)
- `start_run(input) -> {provider_session_id, run_id}`
- `send_message(run_id, message)`
- `stream_events(run_id) -> event stream`
- `cancel_run(run_id)`
- `get_run(run_id) -> normalized status`

### 9.2 Plane Adapter
- `on_assignment_event(payload)`
- `post_task_comment(task_id, body)`
- `update_task_status(task_id, status)`
- `set_task_assignee(task_id, assignee)`
- `append_label(task_id, label)`

## 10. Write-back Templates

### 10.1 Stage started
- Stage, agent profile, start time, expected output.

### 10.2 Stage progress
- Short summary + latest evidence pointer.

### 10.3 Stage completed
- Structured handoff card:
  - Goal
  - Completed
  - Evidence
  - Risks
  - Next actions
  - Confidence

### 10.4 Stage failed
- Failure reason, retries used, escalation request.

## 11. KPI Definitions (V1)

- First-pass approval rate: approvals passed without rejection.
- Mean transition lead time: avg time between stage start and successful handoff.
- Human interventions per task: count of manual approvals + manual unblocks.
- Rejection rate: rejected handoffs / total handoffs.

## 12. Security and Governance

- Enforce project policy at transition boundaries.
- Log all state transitions and approval actions.
- Keep secrets and provider credentials outside task payload.
- Never persist raw private provider credentials in audit payloads.

## 13. Implementation Phases

### Phase 1: Single-agent baseline
- Assignment trigger -> single run -> Plane write-back.

### Phase 2: Serial pipeline
- `coder -> tester -> reviewer` sequential runs with handoff extraction.

### Phase 3: Approval + rejection
- Transition-level approvals and one-level rollback with reason.

### Phase 4: Reliability + KPI
- Retry/fallback, timeout policy, KPI dashboard API.

## 14. API Contract (MVP)

### 14.1 Inbound (from Plane webhook)
- `POST /webhooks/plane/assignment`
- `POST /webhooks/plane/comment` (optional for control commands later)

### 14.2 Internal orchestration
- `POST /task-sessions`
- `GET /task-sessions/{id}`
- `POST /task-sessions/{id}/advance`
- `POST /task-sessions/{id}/block`
- `POST /task-sessions/{id}/resume`

### 14.3 Approval endpoints
- `POST /approvals/{id}/approve`
- `POST /approvals/{id}/reject`

### 14.4 Reporting endpoints
- `GET /metrics/projects/{project_id}`
- `GET /tasks/{task_id}/timeline`

## 15. Acceptance Criteria (V1)

1. Assigning a task to a configured agent profile automatically starts stage execution.
2. A 3-stage serial pipeline can complete end-to-end with Plane write-back.
3. Approval-required transitions pause and resume correctly.
4. Rejection sends work back one stage with mandatory reason.
5. Failure/retry policy works as configured and escalates on exhaustion.
6. KPI endpoints return valid values for completed sessions.
