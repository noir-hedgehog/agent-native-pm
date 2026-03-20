# Plan: Agent-Native PM V1

> Source PRD: /Users/uriah/Documents/AgentRedmine/docs/agent-native-pm-v1-spec.md

## Architectural decisions

Durable decisions that apply across all phases:

- **Routes**:
  - Inbound webhooks: `/webhooks/plane/assignment`, `/webhooks/plane/comment`
  - Orchestration: `/task-sessions/*`
  - Approvals: `/approvals/*`
  - Reporting: `/metrics/projects/{project_id}`, `/tasks/{task_id}/timeline`
- **Schema**:
  - `project_policy`, `task_session`, `agent_run`, `handoff_contract`, `transition_approval`, `audit_event`
- **Key models**:
  - TaskSession owns end-to-end task flow
  - AgentRun maps 1:1 to provider session
  - TransitionApproval gates configured transitions
  - HandoffContract is structured extraction from natural language
- **AuthN/AuthZ**:
  - Webhook signature verification on Plane inbound
  - Project-level policy enforcement on transition boundaries
- **Third-party boundaries**:
  - Plane is source of truth for tasks
  - Agent providers are execution systems of record for raw session logs
  - Orchestrator stores indexes, normalized events, and audit timeline

---

## Phase 1: Assignment Trigger to Single-Agent Run

**User stories**: 1, 4, 5, 7

### What to build

Implement end-to-end baseline where assigning a Plane task to an agent profile creates a TaskSession and one AgentRun, starts provider execution, and writes normalized progress/completion comments back to Plane.

### Acceptance criteria

- [ ] A valid assignment webhook creates exactly one TaskSession and one AgentRun.
- [ ] Duplicate webhook deliveries do not create duplicate runs.
- [ ] Stage start/progress/completion comments are posted to the task.
- [ ] Task state transitions from `todo` to `in_progress` and then to terminal state.
- [ ] Audit events exist for trigger, run start, run completion/failure, and write-back.

---

## Phase 2: Serial Multi-Agent Pipeline

**User stories**: 2, 4, 5, 8, 9

### What to build

Add serial orchestration for configured project pipeline (e.g., `coder -> tester -> reviewer`) with stage-to-stage advancement and per-stage AgentRun creation, while preserving natural-language conversation and normalized handoff extraction.

### Acceptance criteria

- [ ] A project pipeline definition drives stage order deterministically.
- [ ] Each stage produces a new AgentRun with its own provider session id.
- [ ] HandoffContract is extracted and persisted for each succeeded stage.
- [ ] Next stage receives previous handoff context.
- [ ] Final stage completion writes a final summary card to Plane.

---

## Phase 3: Transition Approval and One-Level Rejection

**User stories**: 3, 6, 7, 8

### What to build

Support transition-level approval policies and one-level rollback. For approval-required transitions, pause in `awaiting_review`; on approval continue; on rejection require reason and rerun prior stage.

### Acceptance criteria

- [ ] Approval-required transitions pause and create `transition_approval` records.
- [ ] Approve action resumes pipeline correctly.
- [ ] Reject action requires `reject_reason` and rolls back exactly one stage.
- [ ] Rejected flow creates a new rerun AgentRun for previous stage.
- [ ] Approval timeout policy triggers reminder and blocked behavior.

---

## Phase 4: Reliability, Fallback, and KPI Reporting

**User stories**: 8, 10

### What to build

Add retry/fallback policy and expose KPI/reporting APIs for operational quality. Implement same-agent retry, optional backup-profile fallback, and metrics for approval quality and flow efficiency.

### Acceptance criteria

- [ ] Same-agent retry policy executes once before escalation.
- [ ] Optional backup agent profile is attempted for same stage role.
- [ ] Exhausted failures move task/session to `blocked` or `failed` per policy.
- [ ] KPI endpoint returns first-pass rate, transition lead time, interventions/task, rejection rate.
- [ ] Timeline endpoint returns ordered cross-stage audit trail for one task.
