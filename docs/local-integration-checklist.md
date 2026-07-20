# Local Integration Checklist

## 1. Preconditions

- Python 3.9+
- Repo on `main`
- Port `8080` available

## 2. Quick Run

```bash
./scripts/run_local_smoke.sh
```

Expected output:
- Step 1 returns HTTP `202` with `accepted=true`
- Response includes `agent_run_id` and `completed=true` in default dev mode
- Metrics endpoint returns JSON with `task_count >= 1`
- Timeline endpoint returns webhook + agent run lifecycle events

## 3. Manual Verification

### 3.1 Start service
```bash
PYTHONPATH=src PLANE_WEBHOOK_SECRET=dev-secret python3 -m agentpm.server
```

### 3.2 Send signed assignment webhook
```bash
python3 scripts/send_signed_assignment.py --secret dev-secret
```

### 3.3 Check metrics
```bash
curl -s http://127.0.0.1:8080/metrics/projects/proj_local
```

### 3.4 Check timeline
```bash
curl -s http://127.0.0.1:8080/tasks/task_local_001/timeline
```

## 4. Acceptance Criteria

- Signed request is accepted.
- Replaying same event id returns duplicate=true and no new session.
- Default dev runtime creates one AgentRun and completes it.
- Metrics endpoint responds with KPI fields.
- Timeline endpoint shows ordered webhook, run created, run started, and run completed events.

## 5. Optional Runtime Modes

### 5.1 Durable local state

```bash
AGENTPM_STORE=sqlite \
AGENTPM_SQLITE_PATH=.agentpm/local.sqlite3 \
./scripts/run_local_smoke.sh
```

### 5.2 OpenClaw agent provider

```bash
AGENTPM_AGENT_PROVIDER=openclaw \
OPENCLAW_BASE_URL="$OPENCLAW_BASE_URL" \
OPENCLAW_TOKEN="$OPENCLAW_TOKEN" \
PYTHONPATH=src PLANE_WEBHOOK_SECRET=dev-secret python3 -m agentpm.server
```

### 5.3 Hermes agent provider

```bash
AGENTPM_AGENT_PROVIDER=hermes \
HERMES_BASE_URL="$HERMES_BASE_URL" \
HERMES_TOKEN="$HERMES_TOKEN" \
PYTHONPATH=src PLANE_WEBHOOK_SECRET=dev-secret python3 -m agentpm.server
```

### 5.4 Connector smoke without external credentials

These commands start a local mock agent provider and verify that AgentPM can drive the real HTTP connector path for each provider.

```bash
./scripts/run_connector_smoke.sh openclaw
./scripts/run_connector_smoke.sh hermes
```

### 5.5 Plane local service

```bash
./scripts/plane_service.sh up       # full compose stack
./scripts/plane_service.sh backend  # API/backend-focused local stack
./scripts/plane_service.sh status
```

### 5.6 Real Plane write-back configuration

```bash
export PLANE_API_BASE_URL="http://127.0.0.1:8000"
export PLANE_WORKSPACE_SLUG="<workspace-slug>"
export PLANE_API_TOKEN="<token>"

# Optional when Plane status/state values are UUIDs.
export PLANE_STATUS_FIELD="state"
export PLANE_STATUS_MAP='{"awaiting_review":"<review-state-id>","failed":"<failed-state-id>","done":"<done-state-id>"}'
```

Default Plane API templates:

- Comments: `/api/v1/workspaces/{workspace_slug}/projects/{project_id}/work-items/{task_id}/comments/`
- Work item update: `/api/v1/workspaces/{workspace_slug}/projects/{project_id}/work-items/{task_id}/`

### 5.7 Real MVP smoke

After setting real provider and Plane variables:

```bash
export AGENTPM_AGENT_PROVIDER=openclaw  # or hermes
export REAL_PROJECT_ID="<project-id>"
export REAL_TASK_ID="<issue-id>"
./scripts/run_real_mvp_smoke.sh
```

For a local Plane write-back smoke with a mock agent provider and seeded Plane data:

```bash
./scripts/run_plane_writeback_smoke.sh openclaw
./scripts/run_plane_writeback_smoke.sh hermes
```

## 6. Troubleshooting

1. `INVALID_SIGNATURE`
- Secret mismatch between server and sender script.

2. `Address already in use`
- Stop previous process on 8080 or set `PORT` env.

3. Empty timeline
- Confirm same `task_id` used in webhook and timeline query.

4. No metrics updates
- Confirm `project_id` in webhook matches metrics query path.

5. `HERMES_BASE_URL is required` or `OPENCLAW_BASE_URL is required`
- `AGENTPM_AGENT_PROVIDER` is set to a real provider, but the provider base URL is missing.
