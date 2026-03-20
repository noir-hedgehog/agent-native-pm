# First 5 GitHub Issue Bodies

Parent PRD reference for all issues:
- `/Users/uriah/Documents/AgentRedmine/docs/agent-native-pm-v1-spec.md`

---

## Issue 1: Assignment Webhook Ingestion + Idempotency

### Suggested title
`feat(webhook): ingest plane assignment events with signature check and idempotency`

### Body
```md
## Parent PRD

/Users/uriah/Documents/AgentRedmine/docs/agent-native-pm-v1-spec.md

## What to build

Implement Plane assignment webhook ingestion as the entrypoint of task orchestration. The endpoint must verify webhook signatures, normalize payload fields, generate an idempotency key, and emit one internal trigger event for downstream session creation.

## Acceptance criteria

- [ ] Valid assignment events are accepted and normalized.
- [ ] Invalid signatures are rejected with clear error codes.
- [ ] Duplicate webhook delivery does not create duplicate internal trigger.
- [ ] Trigger and dedupe outcomes are recorded in audit events.

## Blocked by

None - can start immediately.

## User stories addressed

- User story 1
- User story 7
```

---

## Issue 2: TaskSession + AgentRun Persistence Model

### Suggested title
`feat(session): add task_session and agent_run persistence with lifecycle transitions`

### Body
```md
## Parent PRD

/Users/uriah/Documents/AgentRedmine/docs/agent-native-pm-v1-spec.md

## What to build

Create the persistence layer for orchestration entities: project policy, task session, agent run, handoff contract, transition approval, and audit events. Provide basic CRUD/repository operations and lifecycle-safe status transition methods.

## Acceptance criteria

- [ ] Migrations create all core entities required by V1.
- [ ] Task session can be created, loaded, advanced, blocked, and completed.
- [ ] Agent run lifecycle transitions are validated and persisted.
- [ ] Audit event write path exists for key orchestration events.

## Blocked by

- Blocked by Issue 1 (webhook ingestion)

## User stories addressed

- User story 1
- User story 8
- User story 9
```

---

## Issue 3: OpenClaw Adapter V1 (Start/Status/Cancel/Stream)

### Suggested title
`feat(adapter-openclaw): implement normalized run lifecycle adapter`

### Body
```md
## Parent PRD

/Users/uriah/Documents/AgentRedmine/docs/agent-native-pm-v1-spec.md

## What to build

Implement an OpenClaw adapter that maps orchestration commands to provider calls and maps provider states/events into normalized run statuses and event envelopes.

## Acceptance criteria

- [ ] Adapter can start a run and return provider run/session identifiers.
- [ ] Adapter can fetch current run status and map it to normalized states.
- [ ] Adapter can cancel a running session.
- [ ] Adapter event stream emits normalized event envelopes for progress/output/completion/failure.

## Blocked by

- Blocked by Issue 2 (persistence model)

## User stories addressed

- User story 1
- User story 4
- User story 5
```

---

## Issue 4: Plane Write-back Adapter V1

### Suggested title
`feat(adapter-plane): write stage updates and status transitions back to plane`

### Body
```md
## Parent PRD

/Users/uriah/Documents/AgentRedmine/docs/agent-native-pm-v1-spec.md

## What to build

Implement Plane write-back integration for normalized stage updates. Support stage start/progress/completion/failure comments and task state updates according to orchestration state machine.

## Acceptance criteria

- [ ] Stage started/progress/completed/failed comment templates render in Plane.
- [ ] Task status updates map correctly from orchestration states.
- [ ] Write-back failures are retried and audited.
- [ ] Correlation metadata links Plane comments to task session/run identifiers.

## Blocked by

- Blocked by Issue 1 (webhook ingestion)
- Blocked by Issue 2 (persistence model)

## User stories addressed

- User story 4
- User story 5
- User story 7
```

---

## Issue 5: Single-Agent Vertical Slice (E2E)

### Suggested title
`feat(orchestrator): ship assignment-to-completion single-agent end-to-end flow`

### Body
```md
## Parent PRD

/Users/uriah/Documents/AgentRedmine/docs/agent-native-pm-v1-spec.md

## What to build

Deliver the first complete vertical slice from assignment trigger to one agent run completion. This includes trigger ingestion, session/run creation, provider execution via OpenClaw adapter, Plane write-back, handoff contract persistence, and audit timeline.

## Acceptance criteria

- [ ] One assignment creates exactly one task session and one initial agent run.
- [ ] Provider run events are consumed and reflected as Plane progress updates.
- [ ] Completion writes structured handoff and final stage summary to Plane.
- [ ] End-to-end audit trail exists for all key transitions.
- [ ] Replay of the same webhook event does not duplicate execution.

## Blocked by

- Blocked by Issue 3 (OpenClaw adapter)
- Blocked by Issue 4 (Plane write-back adapter)

## User stories addressed

- User story 1
- User story 4
- User story 5
- User story 7
```
