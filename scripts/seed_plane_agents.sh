#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLANE_DIR="${PLANE_DIR:-$ROOT_DIR/plane}"
ENV_FILE="${AGENTPM_PLANE_AGENT_ENV_FILE:-$ROOT_DIR/.agentpm/plane-agent-env.sh}"
REGISTRY_FILE="${AGENTPM_PLANE_AGENT_REGISTRY_FILE:-$ROOT_DIR/.agentpm/plane-agent-registry.json}"
AGENTPM_ROTATE_AGENT_TOKENS="${AGENTPM_ROTATE_AGENT_TOKENS:-0}"

if [ ! -d "$PLANE_DIR" ]; then
  echo "Plane checkout not found at $PLANE_DIR" >&2
  exit 1
fi

OPENCLAW_AGENTS_JSON="$(openclaw agents list --json 2>/dev/null || true)"
export OPENCLAW_AGENTS_JSON
if [ -f "$REGISTRY_FILE" ]; then
  AGENTPM_AGENT_REGISTRY_JSON="$(cat "$REGISTRY_FILE")"
else
  AGENTPM_AGENT_REGISTRY_JSON='{"agents":{}}'
fi
export AGENTPM_AGENT_REGISTRY_JSON
export AGENTPM_ROTATE_AGENT_TOKENS

cd "$PLANE_DIR"

DOCKER=(docker)
if ! docker info >/dev/null 2>&1; then
  DOCKER=(sudo docker)
fi

OUTPUT="$(
"${DOCKER[@]}" compose -f docker-compose.yml exec -T \
  -e OPENCLAW_AGENTS_JSON \
  -e AGENTPM_AGENT_REGISTRY_JSON \
  -e AGENTPM_ROTATE_AGENT_TOKENS \
  api python manage.py shell <<'PY'
import json
import os
import shlex

from plane.db.models import APIToken, Project, ProjectMember, User, Workspace, WorkspaceMember

DEFAULT_AGENTS = {
    "hekate": {
        "display_name": "Hekate",
        "email": "agent-hekate@agentpm.local",
        "username": "agent-hekate",
        "workspace_role": 20,
        "project_role": 20,
        "role_name": "Admin / Coordinator",
    },
    "iris": {
        "display_name": "Iris",
        "email": "agent-iris@agentpm.local",
        "username": "agent-iris",
        "workspace_role": 15,
        "project_role": 15,
        "role_name": "Member / Worker",
    },
    "lingxi": {
        "display_name": "Lingxi",
        "email": "agent-lingxi@agentpm.local",
        "username": "agent-lingxi",
        "workspace_role": 15,
        "project_role": 15,
        "role_name": "Member / Worker",
    },
    "taichi": {
        "display_name": "Taichi",
        "email": "agent-taichi@agentpm.local",
        "username": "agent-taichi",
        "workspace_role": 5,
        "project_role": 5,
        "role_name": "Guest / Observer",
    },
}


def openclaw_agent_ids():
    raw = os.environ.get("OPENCLAW_AGENTS_JSON", "")
    start = raw.find("[")
    if start == -1:
        return []
    try:
        parsed = json.loads(raw[start:])
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(row.get("id")) for row in parsed if isinstance(row, dict) and row.get("id") in DEFAULT_AGENTS]


def registry_agents():
    raw = os.environ.get("AGENTPM_AGENT_REGISTRY_JSON", '{"agents":{}}')
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    rows = parsed.get("agents", parsed)
    if not isinstance(rows, dict):
        return {}
    agents = {}
    for agent_id, spec in rows.items():
        if not isinstance(spec, dict):
            continue
        normalized = str(spec.get("agent_id") or agent_id).strip().lower()
        if not normalized:
            continue
        agents[normalized] = {
            "display_name": str(spec.get("display_name") or normalized.replace("-", " ").title()),
            "email": str(spec.get("email") or f"agent-{normalized}@agentpm.local"),
            "username": str(spec.get("username") or f"agent-{normalized}"),
            "workspace_role": int(spec.get("workspace_role") or 15),
            "project_role": int(spec.get("project_role") or 15),
            "role_name": str(spec.get("role_name") or "Member / Worker"),
        }
    return agents


agent_specs = {**DEFAULT_AGENTS, **registry_agents()}
agent_ids = []
for agent_id in openclaw_agent_ids():
    if agent_id not in agent_ids:
        agent_ids.append(agent_id)
for agent_id in agent_specs:
    if agent_id not in agent_ids:
        agent_ids.append(agent_id)

workspace = Workspace.objects.get(slug="agentpm")
project = Project.objects.get(workspace=workspace, identifier="AGPM")
project.guest_view_all_features = True
project.save()

token_map = {}
user_map = {}

for agent_id in agent_ids:
    spec = agent_specs[agent_id]
    user, _ = User.objects.get_or_create(
        email=spec["email"],
        defaults={
            "username": spec["username"],
            "display_name": spec["display_name"],
            "first_name": spec["display_name"],
            "last_name": "Agent",
            "is_active": True,
            "is_email_verified": True,
            "is_email_valid": True,
            "is_bot": True,
            "bot_type": "WORKSPACE_SEED",
        },
    )
    user.username = spec["username"]
    user.display_name = spec["display_name"]
    user.first_name = spec["display_name"]
    user.last_name = "Agent"
    user.is_active = True
    user.is_email_verified = True
    user.is_email_valid = True
    user.is_bot = True
    user.bot_type = "WORKSPACE_SEED"
    user.set_unusable_password()
    user.save()

    workspace_member, _ = WorkspaceMember.objects.get_or_create(
        workspace=workspace,
        member=user,
        defaults={"role": spec["workspace_role"], "is_active": True},
    )
    workspace_member.role = spec["workspace_role"]
    workspace_member.is_active = True
    workspace_member.save()

    project_member, _ = ProjectMember.objects.get_or_create(
        workspace=workspace,
        project=project,
        member=user,
        defaults={"role": spec["project_role"], "is_active": True},
    )
    project_member.role = spec["project_role"]
    project_member.is_active = True
    project_member.save()

    if os.environ.get("AGENTPM_ROTATE_AGENT_TOKENS") == "1":
        APIToken.objects.filter(user=user, workspace=workspace, is_service=True).delete()

    token, _ = APIToken.objects.get_or_create(
        user=user,
        workspace=workspace,
        label=f"AgentPM {agent_id} MCP",
        is_service=True,
        defaults={
            "description": f"AgentPM MCP token for {spec['display_name']}",
            "user_type": 1,
            "is_active": True,
            "allowed_rate_limit": "1000/min",
        },
    )
    token.description = f"AgentPM MCP token for {spec['display_name']}"
    token.user_type = 1
    token.is_active = True
    token.allowed_rate_limit = "1000/min"
    token.save()

    token_map[agent_id] = token.token
    user_map[agent_id] = {
        "id": str(user.id),
        "email": user.email,
        "username": user.username,
        "display_name": user.display_name,
        "workspace_role": spec["workspace_role"],
        "project_role": spec["project_role"],
        "role_name": spec["role_name"],
    }


def export_line(name, value):
    print(f"export {name}={shlex.quote(value)}")


export_line("PLANE_AGENT_TOKEN_MAP", json.dumps(token_map, sort_keys=True))
export_line("PLANE_AGENT_USER_MAP", json.dumps(user_map, sort_keys=True))
export_line("PLANE_MCP_AGENT_ID", "hekate")
print(f"# Synced Plane agent accounts: {', '.join(agent_ids)}")
print(f"# AgentPM project guest_view_all_features={project.guest_view_all_features}")
PY
)"

mkdir -p "$(dirname "$ENV_FILE")"
printf "%s\n" "$OUTPUT" | /usr/bin/grep '^export ' > "$ENV_FILE"
chmod 600 "$ENV_FILE"
printf "%s\n" "$OUTPUT"
printf "# Wrote agent env file: %s\n" "$ENV_FILE"
