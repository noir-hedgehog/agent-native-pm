# Agent-Native PM V1 Issue Backlog

> Parent PRD: /Users/uriah/Documents/AgentRedmine/docs/agent-native-pm-v1-spec.md
> Plan: /Users/uriah/Documents/AgentRedmine/plans/agent-native-pm-v1-plan.md

## Proposed Slices

1. **Assignment Webhook Ingestion + Idempotency**
- **Type**: AFK
- **Blocked by**: None - can start immediately
- **User stories covered**: 1, 7
- **What to build**: Receive Plane assignment events, verify signatures, persist dedupe keys, and emit normalized internal trigger events.
- **Acceptance criteria**:
  - [ ] Valid assignment events accepted and normalized.
  - [ ] Invalid signatures rejected.
  - [ ] Duplicate delivery does not create duplicate trigger.

2. **TaskSession + AgentRun Persistence Model**
- **Type**: AFK
- **Blocked by**: #1
- **User stories covered**: 1, 8, 9
- **What to build**: Add schema and repositories for task sessions, agent runs, handoff contracts, approvals, and audit events.
- **Acceptance criteria**:
  - [ ] Core tables/collections exist with migration.
  - [ ] Task session lifecycle can be created/read/updated.
  - [ ] Agent run status transitions persist correctly.

3. **OpenClaw Adapter V1 (Start/Status/Cancel/Stream)**
- **Type**: AFK
- **Blocked by**: #2
- **User stories covered**: 1, 4, 5
- **What to build**: Provider adapter implementing normalized run lifecycle on top of OpenClaw session APIs.
- **Acceptance criteria**:
  - [ ] Adapter can start a run and return provider session id.
  - [ ] Adapter maps provider states to normalized run states.
  - [ ] Adapter exposes event stream and cancel behavior.

4. **Plane Write-back Adapter V1**
- **Type**: AFK
- **Blocked by**: #1, #2
- **User stories covered**: 4, 5, 7
- **What to build**: Write stage start/progress/completion/failure comments and task status updates to Plane.
- **Acceptance criteria**:
  - [ ] Comment templates render correctly in Plane.
  - [ ] Task status update mapping is consistent with state machine.
  - [ ] Write failures are retried and audited.

5. **Single-Agent Vertical Slice (E2E)**
- **Type**: AFK
- **Blocked by**: #3, #4
- **User stories covered**: 1, 4, 5, 7
- **What to build**: End-to-end flow from assignment to one agent run completion with full audit trail.
- **Acceptance criteria**:
  - [ ] Assignment starts exactly one run.
  - [ ] Run events propagate to Plane write-back.
  - [ ] Completion updates task and stores handoff contract.

6. **Serial Pipeline Engine (`coder -> tester -> reviewer`)**
- **Type**: AFK
- **Blocked by**: #5
- **User stories covered**: 2, 4, 5, 8
- **What to build**: Stage orchestrator with ordered transitions and per-stage AgentRun creation.
- **Acceptance criteria**:
  - [ ] Pipeline order is deterministic from project policy.
  - [ ] Each stage creates independent agent run/session reference.
  - [ ] Next stage receives previous stage handoff context.

7. **Transition Approval Gate + Timeout Worker**
- **Type**: AFK
- **Blocked by**: #6
- **User stories covered**: 3, 7, 8, 10
- **What to build**: Transition-level approval records, approve/reject APIs, timeout reminder and block behavior.
- **Acceptance criteria**:
  - [ ] Approval-required transitions pause in `awaiting_review`.
  - [ ] Approve continues to next stage.
  - [ ] Timeout worker sends reminder and blocks per policy.

8. **One-Level Rejection and Rerun**
- **Type**: AFK
- **Blocked by**: #7
- **User stories covered**: 6, 8
- **What to build**: Reject previous stage with required reason; spawn rerun for previous stage only.
- **Acceptance criteria**:
  - [ ] Reject requires non-empty reason.
  - [ ] Only immediate previous stage is eligible.
  - [ ] Rerun linked to rejection event in timeline.

9. **Reliability Policy (Retry + Fallback Agent Profile)**
- **Type**: AFK
- **Blocked by**: #8
- **User stories covered**: 8, 10
- **What to build**: Same-agent retry and optional backup-profile attempt for stage failures.
- **Acceptance criteria**:
  - [ ] Retry executes once before fallback.
  - [ ] Fallback uses configured backup profile for same role.
  - [ ] Exhausted failures transition to blocked/failed and notify humans.

10. **KPI + Timeline Reporting API**
- **Type**: AFK
- **Blocked by**: #9
- **User stories covered**: 7, 8, 10
- **What to build**: Project-level KPI endpoint and task timeline endpoint from audit data.
- **Acceptance criteria**:
  - [ ] KPI endpoint returns first-pass rate, lead time, interventions/task, rejection rate.
  - [ ] Timeline endpoint returns ordered cross-stage event stream.
  - [ ] Metric calculations are deterministic and tested.

11. **Policy Configuration UX in Existing Plane Workflow**
- **Type**: HITL
- **Blocked by**: #6
- **User stories covered**: 2, 3, 10
- **What to build**: Minimal operator flow to set pipeline order, approval boundaries, timeout, and allowed actions by role.
- **Acceptance criteria**:
  - [ ] Team can configure one project policy without code changes.
  - [ ] Misconfiguration validation prevents invalid transitions.
  - [ ] Policy changes are versioned/audited.

12. **Production Readiness Review (Runbook + SLO + Oncall Alerts)**
- **Type**: HITL
- **Blocked by**: #10, #11
- **User stories covered**: 7, 8, 10
- **What to build**: Operational checklist for failure modes, alert thresholds, and runbook actions.
- **Acceptance criteria**:
  - [ ] Defined SLO for end-to-end task completion.
  - [ ] Alerts configured for stuck approvals and repeated failures.
  - [ ] Runbook validated with one game-day exercise.

## Suggested First Execution Batch

1. #1 Assignment Webhook Ingestion + Idempotency
2. #2 TaskSession + AgentRun Persistence Model
3. #3 OpenClaw Adapter V1
4. #4 Plane Write-back Adapter V1
5. #5 Single-Agent Vertical Slice (E2E)
