# Hermes Integration Guide

Hermes uses the same normalized Agent Adapter Contract V1 as OpenClaw:

- `start_run(input) -> {provider_run_id, provider_session_id, status}`
- `send_message(provider_run_id, message)`
- `get_run(provider_run_id)`
- `cancel_run(provider_run_id)`
- `stream_events(provider_run_id)`

## 1) Minimum environment

```bash
export AGENTPM_AGENT_PROVIDER="hermes"
export HERMES_BASE_URL="https://<your-hermes-host>"
export HERMES_TOKEN="<bearer-token>"      # optional
export HERMES_API_KEY="<x-api-key>"       # optional
```

## 2) Adapter path mapping

```bash
export HERMES_START_RUN_PATH="/runs"
export HERMES_SEND_MESSAGE_PATH="/runs/{provider_run_id}/messages"
export HERMES_GET_RUN_PATH="/runs/{provider_run_id}"
export HERMES_CANCEL_RUN_PATH="/runs/{provider_run_id}/cancel"
export HERMES_STREAM_EVENTS_PATH="/runs/{provider_run_id}/events"
```

## 3) Adapter field mapping

```bash
export HERMES_RUN_ID_KEY="run_id"          # or id/runId
export HERMES_SESSION_ID_KEY="session_id"  # or sessionId/thread_id
export HERMES_STATUS_KEY="status"          # or state
export HERMES_PROGRESS_KEY="progress"
export HERMES_EVENTS_KEY="events"          # or data
```

## 4) Run AgentPM with Hermes

```bash
AGENTPM_AGENT_PROVIDER=hermes \
HERMES_BASE_URL="$HERMES_BASE_URL" \
HERMES_TOKEN="$HERMES_TOKEN" \
PYTHONPATH=src PLANE_WEBHOOK_SECRET=dev-secret python3 -m agentpm.server
```

## 5) Expected event payload

Completion events should include a `handoff_hint` when possible:

```json
{
  "type": "run.completed",
  "payload": {
    "handoff_hint": {
      "goal": "finish the assigned stage",
      "completed": ["implementation complete"],
      "evidence": ["tests:passed"],
      "risks": [],
      "next_actions": ["reviewer validates"],
      "confidence": "high"
    }
  }
}
```

If Hermes returns different field names or paths, set the `HERMES_*` mapping variables instead of changing orchestrator code.
