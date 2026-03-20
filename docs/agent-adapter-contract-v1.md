# Agent Adapter Contract V1 (OpenClaw + Plane)

## 1. Goal

Define a provider-agnostic orchestration contract with concrete OpenClaw and Plane payload examples.

## 2. Normalized Types

### 2.1 Provider enum
- `openclaw`
- `codex`
- `claude`

### 2.2 Run status enum
- `queued`
- `running`
- `succeeded`
- `failed`
- `canceled`

### 2.3 Event type enum
- `run.started`
- `run.progress`
- `run.output`
- `run.completed`
- `run.failed`
- `run.canceled`

## 3. Orchestrator -> Agent Adapter

### 3.1 Start run
`POST /adapters/{provider}/runs`

Request:
```json
{
  "task_session_id": "ts_01J...",
  "agent_run_id": "ar_01J...",
  "project_id": "proj_123",
  "task_id": "task_456",
  "stage_role": "coder",
  "agent_profile": "openclaw-coder-v1",
  "instruction": "Fix login timeout bug and provide evidence.",
  "context": {
    "task_title": "Login timeout on mobile",
    "task_description": "Users are logged out unexpectedly after token refresh.",
    "previous_handoff": null,
    "attachments": [
      {"type": "url", "value": "https://example.com/logs/abc"}
    ]
  },
  "policy": {
    "allowed_actions": ["read_repo", "run_tests", "write_patch"],
    "max_retry": 1,
    "timeout_seconds": 3600
  }
}
```

Response:
```json
{
  "provider": "openclaw",
  "provider_run_id": "oc_run_789",
  "provider_session_id": "oc_sess_321",
  "status": "queued",
  "started_at": "2026-03-20T14:00:00Z"
}
```

### 3.2 Send follow-up message
`POST /adapters/{provider}/runs/{provider_run_id}/messages`

Request:
```json
{
  "role": "system",
  "content": "Focus on root cause first; avoid broad refactor."
}
```

Response:
```json
{
  "accepted": true,
  "queued_at": "2026-03-20T14:02:00Z"
}
```

### 3.3 Get run status
`GET /adapters/{provider}/runs/{provider_run_id}`

Response:
```json
{
  "provider": "openclaw",
  "provider_run_id": "oc_run_789",
  "provider_session_id": "oc_sess_321",
  "status": "running",
  "progress": {
    "summary": "Identified token refresh race condition",
    "percent": 40
  },
  "updated_at": "2026-03-20T14:07:00Z"
}
```

### 3.4 Cancel run
`POST /adapters/{provider}/runs/{provider_run_id}/cancel`

Response:
```json
{
  "status": "canceled",
  "canceled_at": "2026-03-20T14:10:00Z"
}
```

## 4. Agent Adapter -> Orchestrator Event Stream

Transport can be webhook, SSE, or queue; event schema is fixed.

Event envelope:
```json
{
  "event_id": "evt_01J...",
  "provider": "openclaw",
  "provider_run_id": "oc_run_789",
  "provider_session_id": "oc_sess_321",
  "agent_run_id": "ar_01J...",
  "task_session_id": "ts_01J...",
  "type": "run.output",
  "occurred_at": "2026-03-20T14:08:00Z",
  "payload": {
    "role": "assistant",
    "content": "Root cause found in refresh token retry branch...",
    "artifacts": [
      {"kind": "patch", "uri": "s3://artifacts/patch.diff"},
      {"kind": "test_report", "uri": "s3://artifacts/test.json"}
    ]
  }
}
```

Completion event payload must include normalized summary fields:
```json
{
  "type": "run.completed",
  "payload": {
    "final_message": "Implemented fix and added regression test.",
    "handoff_hint": {
      "goal": "stabilize mobile login token refresh",
      "completed": [
        "patched retry branch",
        "added regression test"
      ],
      "evidence": [
        "test_report:passed",
        "patch:2 files changed"
      ],
      "risks": [
        "needs load test under high latency"
      ],
      "next_actions": [
        "tester validates on iOS and Android"
      ],
      "confidence": "medium"
    }
  }
}
```

## 5. Plane Inbound Webhook Contract

### 5.1 Assignment event (normalized)
`POST /webhooks/plane/assignment`

Request:
```json
{
  "event_id": "plane_evt_123",
  "event_type": "task.assigned",
  "occurred_at": "2026-03-20T13:59:00Z",
  "project": {
    "id": "proj_123",
    "name": "Agent PM"
  },
  "task": {
    "id": "task_456",
    "key": "AG-42",
    "title": "Login timeout on mobile",
    "description": "Investigate and fix token refresh timeout",
    "status": "todo"
  },
  "assignee": {
    "id": "agent_openclaw_coder",
    "type": "agent_profile"
  },
  "actor": {
    "id": "user_999",
    "name": "Uriah"
  },
  "signature": "sha256=..."
}
```

Response:
```json
{
  "accepted": true,
  "task_session_id": "ts_01J...",
  "idempotency_key": "plane_evt_123:task_456"
}
```

## 6. Orchestrator -> Plane Write-back

### 6.1 Stage started comment
`POST /plane/tasks/{task_id}/comments`

Request:
```json
{
  "body": "[Stage Started] role=coder agent=openclaw-coder-v1 started_at=2026-03-20T14:00:00Z"
}
```

### 6.2 Stage progress comment
```json
{
  "body": "[Stage Progress] role=coder summary=Identified token refresh race condition evidence=test-log://abc"
}
```

### 6.3 Stage completed comment (structured card in text)
```json
{
  "body": "[Stage Completed]\nGoal: stabilize mobile login token refresh\nCompleted: patched retry branch; added regression test\nEvidence: test_report:passed; patch:2 files changed\nRisks: needs load test under high latency\nNext: tester validates on iOS and Android\nConfidence: medium"
}
```

### 6.4 Task status update
`PATCH /plane/tasks/{task_id}`

Request:
```json
{
  "status": "awaiting_review"
}
```

## 7. Error Contract

Error envelope:
```json
{
  "error": {
    "code": "ADAPTER_TIMEOUT",
    "message": "Provider did not return status within timeout",
    "retryable": true,
    "details": {
      "provider": "openclaw",
      "provider_run_id": "oc_run_789"
    }
  }
}
```

Common codes:
- `INVALID_SIGNATURE`
- `IDEMPOTENCY_CONFLICT`
- `ADAPTER_UNAVAILABLE`
- `ADAPTER_TIMEOUT`
- `POLICY_VIOLATION`
- `APPROVAL_REQUIRED`
- `TRANSITION_NOT_ALLOWED`

## 8. Contract Test Matrix (Minimum)

1. Assignment webhook accepted once, deduped on replay.
2. OpenClaw run start returns provider ids and queued/running state.
3. Event stream maps provider events to normalized event types.
4. Completion event produces handoff extraction and Plane completed comment.
5. Transition requiring approval blocks progression.
6. Rejection allows only one-stage rollback.
7. Adapter timeout triggers retry/fallback policy.
