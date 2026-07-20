# MVP Readiness

## Verified locally

Run all local checks:

```bash
./scripts/verify_mvp.sh
```

Current local MVP evidence:

- Plane API responds at `http://127.0.0.1:8000/` with `{"status":"OK"}`.
- Plane web/proxy responds at `http://127.0.0.1/`.
- AgentPM accepts signed Plane assignment webhooks.
- AgentPM creates a TaskSession and AgentRun.
- AgentPM consumes agent progress/completion events.
- AgentPM stores audit timeline events.
- Project metrics and task timeline endpoints respond.
- OpenClaw connector path is verified through a local HTTP mock provider.
- Hermes connector path is verified through a local HTTP mock provider.
- Plane write-back is verified against the local Plane API using a seeded workspace/project/work item/API token.
- Python regression suite passes.

## Local service commands

```bash
./scripts/plane_service.sh backend
./scripts/run_local_smoke.sh
./scripts/run_connector_smoke.sh openclaw
./scripts/run_connector_smoke.sh hermes
./scripts/run_plane_writeback_smoke.sh openclaw
./scripts/run_plane_writeback_smoke.sh hermes
```

## Real provider cutover

OpenClaw:

```bash
export AGENTPM_AGENT_PROVIDER=openclaw
export OPENCLAW_BASE_URL="https://<openclaw-host>"
export OPENCLAW_TOKEN="<optional-bearer-token>"
export OPENCLAW_API_KEY="<optional-api-key>"
```

Hermes:

```bash
export AGENTPM_AGENT_PROVIDER=hermes
export HERMES_BASE_URL="https://<hermes-host>"
export HERMES_TOKEN="<optional-bearer-token>"
export HERMES_API_KEY="<optional-api-key>"
```

Both connectors support path and field remapping through `OPENCLAW_*` or `HERMES_*` variables documented in:

- `docs/openclaw-integration.md`
- `docs/hermes-integration.md`

## Real Plane write-back cutover

Required:

```bash
export PLANE_API_BASE_URL="http://127.0.0.1:8000"
export PLANE_WORKSPACE_SLUG="<workspace-slug>"
export PLANE_API_TOKEN="<token>"
```

If Plane states are UUID-backed, map AgentPM statuses:

```bash
export PLANE_STATUS_FIELD="state"
export PLANE_STATUS_MAP='{"awaiting_review":"<review-state-id>","failed":"<failed-state-id>","done":"<done-state-id>"}'
```

Default paths:

- `/api/v1/workspaces/{workspace_slug}/projects/{project_id}/work-items/{task_id}/comments/`
- `/api/v1/workspaces/{workspace_slug}/projects/{project_id}/work-items/{task_id}/`

## Local Plane write-back verification

Seed a local Plane workspace/project/work item/API token:

```bash
./scripts/seed_plane_mvp.sh
```

Run provider connector plus real local Plane write-back:

```bash
./scripts/run_plane_writeback_smoke.sh openclaw
./scripts/run_plane_writeback_smoke.sh hermes
```

## Remaining production validation

The local MVP is runnable, local Plane write-back is verified, and the HTTP connector contracts are verified with a mock provider. Production completion still requires one successful run against each real external agent provider:

- A real OpenClaw run using `OPENCLAW_BASE_URL`.
- A real Hermes run using `HERMES_BASE_URL`.
- A real Plane write-back to the target non-local Plane environment, if production will not use the local Plane instance.

Use the real smoke script after setting the provider and Plane variables:

```bash
export AGENTPM_AGENT_PROVIDER=openclaw  # or hermes
export OPENCLAW_BASE_URL="https://<openclaw-host>"
# export HERMES_BASE_URL="https://<hermes-host>"
export PLANE_API_BASE_URL="http://127.0.0.1:8000"
export PLANE_WORKSPACE_SLUG="<workspace-slug>"
export PLANE_API_TOKEN="<token>"
export REAL_PROJECT_ID="<project-id>"
export REAL_TASK_ID="<issue-id>"
export REAL_AGENT_ASSIGNEE="agent_openclaw_coder"

./scripts/run_real_mvp_smoke.sh
```

The script starts AgentPM with the configured provider, sends a signed Plane assignment webhook for the existing work item, validates the AgentRun lifecycle in the timeline, and relies on the configured Plane write-back adapter to post comments and update state.
