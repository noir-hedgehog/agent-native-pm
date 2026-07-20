# OpenClaw Integration Guide

## 0) Preferred direction: Plane-native MCP tools

Expose Plane to OpenClaw through Plane's built-in Streamable HTTP MCP endpoint:

```bash
./scripts/plane_service.sh backend
./scripts/seed_plane_agents.sh
./scripts/register_plane_native_mcp_openclaw.sh
./scripts/install_plane_agent_skill.sh
```

Verify OpenClaw can see the tools:

```bash
openclaw mcp probe plane-native-hekate --json
```

Seed the Agent-facing guide into the current Plane project:

```bash
./scripts/seed_plane_agent_guide_page.sh
```

Available tools are namespaced by the registered OpenClaw server, for example `plane-native-hekate__plane_list_projects`:

- `plane_get_me`
- `plane_list_projects`
- `plane_list_states`
- `plane_list_work_items`
- `plane_search_work_items`
- `plane_get_work_item`
- `plane_get_project_summary`
- `plane_list_project_members`
- `plane_list_labels`
- `plane_summarize_work_item`
- `plane_add_comment`
- `plane_update_status`
- `plane_update_work_item`
- `plane_assign_work_item`
- `plane_add_project_member`
- `plane_add_workspace_user_to_project`
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

Plane-native MCP uses the Plane API token in `X-Api-Key` as the identity. It does not accept `agent_id` switching in tool arguments. Role behavior:

- `hekate`: admin/coordinator; can read, comment, assign, create projects/work items, update work items, and manage work item links/relations.
- `iris`: member/worker; can read, comment, create work items, and update/link/relate only assigned work items.
- `lingxi`: member/worker; can read, comment, create work items, and update/link/relate only assigned work items.
- `taichi`: guest/observer; can read and comment, cannot update work items or links/relations.

Agents should use the `agentpm-plane-workflow` skill before calling these tools. The skill requires the agent to gather `project_id`, project members, and states before writing. It also defines canonical parameter rules:

- `target_agent_id` and `member_agent_id` are short agent ids such as `iris`, not Plane user UUIDs or emails.
- `project_id` comes from `plane_list_projects`.
- `state`/`status` comes from `plane_list_states`.
- Project membership is changed only by Admin tools; workspace invitations stay in Plane UI or the human-admin CLI.

Approved dynamic agents are stored in `.agentpm/plane-agent-registry.json`. Agent tokens are written to `.agentpm/plane-agent-env.sh`. Both files are ignored by git.

Unknown agents can only submit a bootstrap request through the local AgentPM CLI or legacy wrapper:

```bash
python3 scripts/plane_cli.py request-agent-registration atlas "Atlas" \
  --requested-role member \
  --project-id "$REAL_PROJECT_ID" \
  --reason "Join the project"
```

Human admins approve or reject locally:

```bash
python3 scripts/plane_agent_admin.py list-applications --status pending
python3 scripts/plane_agent_admin.py approve app-... --role member --project-id "$REAL_PROJECT_ID"
python3 scripts/plane_agent_admin.py add-agent atlas "Atlas" --role member --project-id "$REAL_PROJECT_ID"
```

Approval creates/updates the Plane bot user, membership, token, registry entry, and env token map. Hekate can see application summaries through `plane_list_agent_accounts`, but approval remains a human-admin CLI action.

For real agent use, register one Plane-native MCP server per Plane agent identity:

```bash
AGENTPM_MCP_AGENT_ID=iris ./scripts/register_plane_native_mcp_openclaw.sh
openclaw mcp probe plane-native-iris --json
```

This creates a Streamable HTTP MCP server config pointing at `/api/v1/workspaces/<slug>/mcp/` and authenticating with Iris's Plane API token. Plane resolves the token to Iris and applies project-role policy inside Plane.

Tailscale access reuses the Plane URL:

```bash
AGENTPM_MCP_AGENT_ID=iris \
  ./scripts/register_plane_native_mcp_openclaw.sh \
  http://uriahmac-mini.tail3b7a05.ts.net/api/v1/workspaces/agentpm/mcp/
```

The older stdio MCP wrapper is still available for local debugging:

```bash
./scripts/register_plane_mcp_openclaw.sh
```

Plane workspace admins can manage these agent tokens in Plane under workspace member settings. Agent users appear as `Agent`, human users as `Human`, and only agent rows expose token controls. Token values are returned once when created; later lists show metadata only.

Direct CLI debugging uses the same API layer:

```bash
eval "$(./scripts/seed_plane_mvp.sh | /usr/bin/grep '^export ')"
eval "$(./scripts/seed_plane_agents.sh | /usr/bin/grep '^export ')"
python3 scripts/plane_cli.py work-items --limit 10
python3 scripts/plane_cli.py work-items --agent-id iris --limit 10
python3 scripts/plane_cli.py summary "$REAL_TASK_ID"
python3 scripts/plane_cli.py create-project "Agent Sandbox" AGSB --agent-id hekate --member-agent-id iris
python3 scripts/plane_cli.py create-work-item "$REAL_PROJECT_ID" "Draft project plan" iris --agent-id iris
```

## 1) Minimum environment

```bash
export OPENCLAW_BASE_URL="https://<your-openclaw-host>"
export OPENCLAW_TOKEN="<bearer-token>"            # optional
export OPENCLAW_API_KEY="<x-api-key>"             # optional
export AGENTPM_AGENT_PROVIDER="openclaw"
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

The probe accepts `ws://` and `wss://` base URLs and converts them to HTTP/HTTPS for endpoint checks.

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
3. Start AgentPM with `AGENTPM_AGENT_PROVIDER=openclaw`.
4. Run one task in a non-production Plane project.
5. Validate timeline + metrics endpoints update correctly.

```bash
AGENTPM_AGENT_PROVIDER=openclaw \
OPENCLAW_BASE_URL="$OPENCLAW_BASE_URL" \
OPENCLAW_TOKEN="$OPENCLAW_TOKEN" \
PYTHONPATH=src PLANE_WEBHOOK_SECRET=dev-secret python3 -m agentpm.server
```
