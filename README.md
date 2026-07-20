# agent-native-pm

MVP orchestrator for Plane assignment webhook ingestion, signature validation, idempotency, agent run orchestration, Plane write-back, and audit/KPI reporting.

## Run server

```bash
PYTHONPATH=src PLANE_WEBHOOK_SECRET=dev-secret python3 -m agentpm.server
```

By default the service runs in local dev mode:

- `DevAgentAdapter` emits deterministic progress/completion events.
- `DevPlaneWritebackAdapter` records write-back calls in memory instead of requiring Plane credentials.
- `InMemoryStore` is used unless `AGENTPM_STORE=sqlite` is set.

Server endpoint:

- `POST /webhooks/plane/assignment`

Required header:

- `X-Plane-Signature: <hmac_hex>` (also accepts `sha256=<hmac_hex>`)

## Run tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Verify the MVP

This runs the local Plane service check, Python tests, AgentPM dev smoke, and OpenClaw/Hermes connector smokes:

```bash
./scripts/verify_mvp.sh
```

Readiness notes:

- `docs/mvp-readiness.md`

## Production deployment

AgentPM runs beside Plane on the same Docker network, with Plane exposing read-only AgentPM views under `/agentpm/` and authenticated Admin writes through Plane API endpoints.

```bash
./scripts/install_openclaw_bridge.sh
./scripts/deploy_remote.sh --plane
./scripts/check_remote.sh
```

Current Tailscale service: `http://100.79.187.62:8080/`. See `docs/production-deployment.md` for first deployment, backup, rollback, and exposure rules.

## Local smoke test (real request flow)

Use this to validate:
- signed webhook ingestion
- task session creation + idempotency
- dev agent run creation/start/completion
- metrics and timeline query endpoints

```bash
./scripts/run_local_smoke.sh
```

Manual equivalent:

```bash
# 1) start server
PYTHONPATH=src PLANE_WEBHOOK_SECRET=dev-secret python3 -m agentpm.server

# 2) send one signed assignment webhook (new terminal)
python3 scripts/send_signed_assignment.py --secret dev-secret

# 3) check project metrics
curl -s http://127.0.0.1:8080/metrics/projects/proj_local

# 4) check task timeline
curl -s http://127.0.0.1:8080/tasks/task_local_001/timeline
```

## Runtime configuration

Use SQLite for local durable state:

```bash
AGENTPM_STORE=sqlite \
AGENTPM_SQLITE_PATH=.agentpm/local.sqlite3 \
PYTHONPATH=src PLANE_WEBHOOK_SECRET=dev-secret python3 -m agentpm.server
```

Use OpenClaw:

```bash
AGENTPM_AGENT_PROVIDER=openclaw \
OPENCLAW_BASE_URL="$OPENCLAW_BASE_URL" \
OPENCLAW_TOKEN="$OPENCLAW_TOKEN" \
PYTHONPATH=src PLANE_WEBHOOK_SECRET=dev-secret python3 -m agentpm.server
```

Use Hermes:

```bash
AGENTPM_AGENT_PROVIDER=hermes \
HERMES_BASE_URL="$HERMES_BASE_URL" \
HERMES_TOKEN="$HERMES_TOKEN" \
PYTHONPATH=src PLANE_WEBHOOK_SECRET=dev-secret python3 -m agentpm.server
```

Enable Plane write-back over HTTP:

```bash
PLANE_API_BASE_URL="http://127.0.0.1:8000" \
PLANE_WORKSPACE_SLUG="<workspace-slug>" \
PLANE_API_TOKEN="<token>" \
PYTHONPATH=src PLANE_WEBHOOK_SECRET=dev-secret python3 -m agentpm.server
```

For real Plane, AgentPM uses these default API templates:

- comments: `/api/v1/workspaces/{workspace_slug}/projects/{project_id}/work-items/{task_id}/comments/`
- work item update: `/api/v1/workspaces/{workspace_slug}/projects/{project_id}/work-items/{task_id}/`

If your Plane state values are UUIDs, map internal statuses to Plane state ids:

```bash
export PLANE_STATUS_FIELD="state"
export PLANE_STATUS_MAP='{"awaiting_review":"<review-state-id>","failed":"<failed-state-id>","done":"<done-state-id>"}'
```

The path templates and comment field can also be overridden:

```bash
export PLANE_COMMENT_PATH_TEMPLATE="/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/{task_id}/comments/"
export PLANE_TASK_PATH_TEMPLATE="/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/{task_id}/"
export PLANE_COMMENT_BODY_FIELD="comment_html"
```

## Plane local service

This repo treats `./plane` as a local checkout of upstream Plane, not as AgentPM source code.

```bash
# full Plane compose stack
./scripts/plane_service.sh up

# backend/API-oriented local stack
./scripts/plane_service.sh backend

# inspect/stop
./scripts/plane_service.sh status
./scripts/plane_service.sh down
```

### Plane over Tailscale

Plane's local proxy publishes port 80 on this machine, so other devices in the same tailnet can use:

```bash
./scripts/plane_tailscale.sh
```

Current local access pattern:

- Tailscale IP URL: `http://100.118.86.67/`
- MagicDNS URL: `http://uriahmac-mini.tail3b7a05.ts.net/`

For a Tailscale Serve-managed HTTPS endpoint, first enable Serve for the tailnet when prompted by Tailscale, then run:

```bash
./scripts/plane_tailscale.sh serve
```

## OpenClaw and Hermes integration

See:
- `docs/openclaw-integration.md`
- `docs/hermes-integration.md`

Quick probe:

```bash
python3 scripts/openclaw_probe.py --base-url "$OPENCLAW_BASE_URL"
```

Local connector smoke tests use a mock HTTP agent provider and exercise the real OpenClaw/Hermes adapters through `agentpm.server`:

```bash
./scripts/run_connector_smoke.sh openclaw
./scripts/run_connector_smoke.sh hermes
```

Local Plane write-back smoke seeds Plane data and verifies AgentPM comments/state updates against the running Plane API:

```bash
./scripts/run_plane_writeback_smoke.sh openclaw
./scripts/run_plane_writeback_smoke.sh hermes
```

### Plane-native MCP for OpenClaw

The preferred integration direction is Plane's built-in MCP endpoint. OpenClaw connects to Plane over HTTP, using the Agent's own Plane API token. No separate AgentRedmine MCP daemon or SSH access is required.

Register Hekate against local Plane:

```bash
./scripts/register_plane_native_mcp_openclaw.sh
```

Install or refresh the shared Plane workflow skill for Codex and OpenClaw:

```bash
./scripts/install_plane_agent_skill.sh
```

Register a locked Agent identity:

```bash
AGENTPM_MCP_AGENT_ID=iris ./scripts/register_plane_native_mcp_openclaw.sh
openclaw mcp probe plane-native-iris --json
```

Use the Tailscale Plane URL from another machine:

```bash
AGENTPM_MCP_AGENT_ID=iris \
  ./scripts/register_plane_native_mcp_openclaw.sh \
  http://uriahmac-mini.tail3b7a05.ts.net/api/v1/workspaces/agentpm/mcp/
```

The native MCP endpoint is:

```text
/api/v1/workspaces/<workspace-slug>/mcp/
```

It authenticates with Plane's `X-Api-Key` header. The token selects the Plane user, so MCP calls cannot switch identity with an `agent_id` argument.

Agents should use the `agentpm-plane-workflow` skill before writing. It standardizes the flow `plane_list_projects` -> `plane_list_project_members` -> `plane_list_states` -> write tool, and requires short canonical agent ids such as `iris` for `target_agent_id`/`member_agent_id`.

Seed the in-project agent guide Page:

```bash
./scripts/seed_plane_agent_guide_page.sh
```

Source docs:

- `docs/agent-plane-mcp-guide.md`
- `docs/plane-api-mcp-coverage.md`
- `docs/plane-ce-compliance-notes.md`

The legacy local stdio MCP server remains available for debugging:

```bash
./scripts/register_plane_mcp_openclaw.sh
```

Codex can use the legacy stdio server through:

```bash
scripts/plane_mcp_stdio.sh
```

Initialize distinct Plane identities for the current OpenClaw agents:

```bash
./scripts/seed_plane_agents.sh
```

This creates the default Hekate, Iris, Lingxi, and Taichi Plane bot users, also syncs any approved agents in `.agentpm/plane-agent-registry.json`, writes token/user maps to `.agentpm/plane-agent-env.sh`, and enables guest read/comment behavior for the AgentPM MVP project. MCP tools accept an optional `agent_id`; if omitted, `PLANE_MCP_AGENT_ID` is used and defaults to `hekate`.

For real agent registrations, prefer one locked MCP server per agent identity:

```bash
AGENTPM_MCP_AGENT_ID=iris ./scripts/register_plane_mcp_openclaw.sh
openclaw mcp probe agentpm-plane-iris --json
```

The locked server sets `PLANE_MCP_LOCKED_AGENT_ID`; requests with another `agent_id` are rejected instead of switching identity. The shared `agentpm-plane` registration is useful for local admin/debug workflows.

Plane workspace admins can also manage agent tokens from the Plane member settings page. Bot users are shown as `Agent`, human users as `Human`, and only agent rows expose token management. Token values are shown once on creation; token lists do not expose secret values.

Unknown agents can request access without a Plane token:

```bash
python3 scripts/plane_cli.py request-agent-registration atlas "Atlas" \
  --requested-role member \
  --project-id "$REAL_PROJECT_ID" \
  --reason "Join the AgentPM workflow"
```

A human admin approves or rejects applications locally:

```bash
python3 scripts/plane_agent_admin.py list-applications --status pending
python3 scripts/plane_agent_admin.py approve app-... --role member --project-id "$REAL_PROJECT_ID"
python3 scripts/plane_agent_admin.py reject app-... --reason "Not needed yet"
```

The approval flow creates/updates the Plane bot user, workspace/project membership, an agent API token, `.agentpm/plane-agent-registry.json`, and `.agentpm/plane-agent-env.sh`. To add an agent directly without an application:

```bash
python3 scripts/plane_agent_admin.py add-agent atlas "Atlas" --role member --project-id "$REAL_PROJECT_ID"
```

OpenClaw will expose these tools under the `agentpm-plane` server:

- `plane_get_me`
- `plane_list_projects`
- `plane_list_states`
- `plane_list_work_items`
- `plane_search_work_items`
- `plane_get_work_item`
- `plane_get_project_summary`
- `plane_list_project_members`
- `plane_list_labels`
- `plane_list_work_item_kinds`
- `plane_summarize_work_item`
- `plane_add_comment`
- `plane_update_status`
- `plane_update_work_item`
- `plane_assign_work_item`
- `plane_create_project`
- `plane_create_work_item`
- `plane_list_work_item_comments`
- `plane_list_work_item_activity`
- `plane_list_work_item_links`
- `plane_add_work_item_link`
- `plane_update_work_item_link`
- `plane_delete_work_item_link`
- `plane_list_work_item_relations`
- `plane_add_work_item_relation`
- `plane_delete_work_item_relation`
- `plane_list_agent_accounts`
- `plane_list_cycles`
- `plane_create_cycle`
- `plane_add_work_item_to_cycle`
- `plane_remove_work_item_from_cycle`
- `plane_list_modules`
- `plane_create_module`
- `plane_add_work_item_to_module`
- `plane_remove_work_item_from_module`

Human/script CLI access uses the same Plane API layer:

```bash
eval "$(./scripts/seed_plane_mvp.sh | /usr/bin/grep '^export ')"
eval "$(./scripts/seed_plane_agents.sh | /usr/bin/grep '^export ')"
python3 scripts/plane_cli.py work-items --limit 10
python3 scripts/plane_cli.py work-items --agent-id iris --limit 10
python3 scripts/plane_cli.py summary "$REAL_TASK_ID"
python3 scripts/plane_cli.py create-project "Agent Sandbox" AGSB --agent-id hekate --member-agent-id iris
python3 scripts/plane_cli.py create-work-item "$REAL_PROJECT_ID" "Draft project plan" iris --agent-id iris
```

When real provider and Plane credentials are available, run the real MVP smoke:

```bash
AGENTPM_AGENT_PROVIDER=openclaw \
OPENCLAW_BASE_URL="$OPENCLAW_BASE_URL" \
PLANE_API_BASE_URL="http://127.0.0.1:8000" \
PLANE_WORKSPACE_SLUG="<workspace-slug>" \
PLANE_API_TOKEN="<token>" \
REAL_PROJECT_ID="<project-id>" \
REAL_TASK_ID="<issue-id>" \
./scripts/run_real_mvp_smoke.sh
```
