#!/usr/bin/env bash
set -euo pipefail

# Create the first 5 implementation issues in dependency order.
# Preconditions:
# 1) gh installed and authenticated
# 2) current repo has GitHub remote
# 3) run from repo root

if ! command -v gh >/dev/null 2>&1; then
  echo "ERROR: gh is not installed. Install GitHub CLI first." >&2
  exit 1
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  echo "ERROR: git remote 'origin' is not configured." >&2
  exit 1
fi

create_issue() {
  local title="$1"
  local body="$2"
  gh issue create --title "$title" --body "$body"
}

body1=$(cat <<'MD'
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
MD
)

body2=$(cat <<'MD'
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
MD
)

body3=$(cat <<'MD'
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
MD
)

body4=$(cat <<'MD'
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
MD
)

body5=$(cat <<'MD'
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
MD
)

echo "Creating issues in dependency order..."
create_issue "feat(webhook): ingest plane assignment events with signature check and idempotency" "$body1"
create_issue "feat(session): add task_session and agent_run persistence with lifecycle transitions" "$body2"
create_issue "feat(adapter-openclaw): implement normalized run lifecycle adapter" "$body3"
create_issue "feat(adapter-plane): write stage updates and status transitions back to plane" "$body4"
create_issue "feat(orchestrator): ship assignment-to-completion single-agent end-to-end flow" "$body5"

echo "Done."
