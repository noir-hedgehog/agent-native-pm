# OpenClaw Integration Guide

## 1) Minimum environment

```bash
export OPENCLAW_BASE_URL="https://<your-openclaw-host>"
export OPENCLAW_TOKEN="<bearer-token>"            # optional
export OPENCLAW_API_KEY="<x-api-key>"             # optional
```

## 2) Probe connectivity

```bash
python3 scripts/openclaw_probe.py \
  --base-url "$OPENCLAW_BASE_URL" \
  --token "$OPENCLAW_TOKEN" \
  --api-key "$OPENCLAW_API_KEY"
```

If `/health` is not available, change probe path:

```bash
python3 scripts/openclaw_probe.py \
  --base-url "$OPENCLAW_BASE_URL" \
  --health-path "/api/healthz" \
  --runs-path "/api/runs"
```

## 3) Adapter path mapping (no code changes)

```bash
export OPENCLAW_START_RUN_PATH="/runs"
export OPENCLAW_SEND_MESSAGE_PATH="/runs/{provider_run_id}/messages"
export OPENCLAW_GET_RUN_PATH="/runs/{provider_run_id}"
export OPENCLAW_CANCEL_RUN_PATH="/runs/{provider_run_id}/cancel"
export OPENCLAW_STREAM_EVENTS_PATH="/runs/{provider_run_id}/events"
```

## 4) Adapter field mapping (no code changes)

```bash
export OPENCLAW_RUN_ID_KEY="run_id"          # or id/runId
export OPENCLAW_SESSION_ID_KEY="session_id"  # or sessionId/thread_id
export OPENCLAW_STATUS_KEY="status"          # or state
export OPENCLAW_PROGRESS_KEY="progress"
export OPENCLAW_EVENTS_KEY="events"          # or data
```

## 5) Recommended rollout

1. Probe connectivity (`openclaw_probe.py`).
2. Configure path/field mappings by env vars.
3. Run one task in non-production project.
4. Validate timeline + metrics endpoints update correctly.
