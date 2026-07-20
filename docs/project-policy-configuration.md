# Project Policy Configuration V1

Project policies define the serial AgentPM pipeline for one Plane project. AgentPM reads the latest published policy when an assignment webhook arrives; projects without a policy keep using the existing dev fallback.

## AgentPM API

- `GET /policies/projects/{project_id}` returns the latest policy.
- `GET /policies/projects/{project_id}/history` returns all policy versions.
- `POST /policies/projects/{project_id}` publishes a new immutable version.

The local server enables CORS for the Plane settings UI. Override the UI target with `VITE_AGENTPM_API_BASE_URL`; otherwise it uses `http://127.0.0.1:8080`.

## CLI

```bash
scripts/agentpm_policy_cli.py get <project_id>
scripts/agentpm_policy_cli.py history <project_id>
scripts/agentpm_policy_cli.py publish <project_id> --file policy.json
```

Set `AGENTPM_BASE_URL` to target a non-default AgentPM server.

## MCP

The Plane MCP server exposes:

- `plane_get_project_policy`, available to registered agents with read access
- `plane_publish_project_policy`, limited to Admin project-role agents such as Hekate

Both tools call the AgentPM policy API through `AGENTPM_BASE_URL`.

## Plane UI

Open project settings, then choose `Agent Policy` under `Execution`.

The V1 form stores:

- pipeline roles, one per line
- role-to-agent mapping as `role=agent_id`
- approval gates as transition keys, for example `tester->reviewer`
- reminder and block timeout hours
- allowed actions as `role=action_a,action_b`
- publisher and change note

## Policy JSON Example

```json
{
  "pipeline_definition": ["coder", "tester", "reviewer"],
  "agent_profile_by_role": {
    "coder": "iris",
    "tester": "lingxi",
    "reviewer": "hekate"
  },
  "transition_approval_rules": {
    "coder->tester": false,
    "tester->reviewer": true,
    "reviewer->done": true
  },
  "transition_timeout_hours": {
    "reminder": 24,
    "block": 72
  },
  "allowed_actions_by_role": {
    "coder": ["read_plane", "comment", "create_work_item"],
    "tester": ["read_plane", "comment", "update_status"],
    "reviewer": ["read_plane", "comment", "update_status"]
  },
  "published_by": "human-admin",
  "change_note": "Initial project workflow"
}
```

Validation requires at least one role, no duplicate roles, adjacent transition approval keys or final `role->done`, positive timeouts with `block > reminder`, and at least one allowed action for every role.
