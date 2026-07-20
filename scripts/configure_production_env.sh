#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env.agentpm"
PLANE_ENV_FILE="$ROOT_DIR/plane/.env"
AGENT_ENV_FILE="$ROOT_DIR/.agentpm/plane-agent-env.sh"
BRIDGE_ENV_FILE="$ROOT_DIR/.agentpm/openclaw-bridge.env"

set_env() {
  local file="$1" key="$2" value="$3" temp
  temp="$(mktemp)"
  awk -v key="$key" -F= '$1 != key { print }' "$file" > "$temp"
  printf '%s=%s\n' "$key" "$value" >> "$temp"
  chmod 600 "$temp"
  mv "$temp" "$file"
}

if [ ! -f "$ENV_FILE" ]; then
  cp "$ROOT_DIR/.env.agentpm.example" "$ENV_FILE"
fi
chmod 600 "$ENV_FILE"

if [ ! -f "$AGENT_ENV_FILE" ]; then
  echo "Missing $AGENT_ENV_FILE; seed or approve the Hekate Agent account first." >&2
  exit 2
fi

# shellcheck disable=SC1090
source "$AGENT_ENV_FILE"
hekate_token="$(PLANE_AGENT_TOKEN_MAP="$PLANE_AGENT_TOKEN_MAP" python3 -c 'import json, os; print(json.loads(os.environ["PLANE_AGENT_TOKEN_MAP"])["hekate"])')"

admin_token="$(awk -F= '$1 == "AGENTPM_ADMIN_TOKEN" && $2 !~ /^replace-/ {sub(/^[^=]*=/, ""); print; exit}' "$ENV_FILE")"
webhook_secret="$(awk -F= '$1 == "PLANE_WEBHOOK_SECRET" && $2 !~ /^replace-/ {sub(/^[^=]*=/, ""); print; exit}' "$ENV_FILE")"
[ -n "$admin_token" ] || admin_token="$(openssl rand -hex 32)"
[ -n "$webhook_secret" ] || webhook_secret="$(openssl rand -hex 32)"

status_map="$(cd "$ROOT_DIR/plane" && sudo docker compose exec -T api python manage.py shell <<'PY'
import json
from plane.db.models import Project, State

project = Project.objects.filter(workspace__slug="agentpm", identifier="AGPM").first()
if project is None:
    raise SystemExit("AgentPM MVP project not found")
states = {item.name: str(item.id) for item in State.objects.filter(project=project)}
required = {"awaiting_review": "Awaiting Review", "failed": "Failed", "done": "Done"}
missing = [name for name in required.values() if name not in states]
if missing:
    raise SystemExit(f"Missing AgentPM states: {', '.join(missing)}")
print(json.dumps({key: states[name] for key, name in required.items()}, separators=(",", ":")))
PY
)"

set_env "$ENV_FILE" AGENTPM_ADMIN_TOKEN "$admin_token"
set_env "$ENV_FILE" PLANE_WEBHOOK_SECRET "$webhook_secret"
set_env "$ENV_FILE" PLANE_API_BASE_URL "http://api:8000"
set_env "$ENV_FILE" PLANE_WORKSPACE_SLUG "agentpm"
set_env "$ENV_FILE" PLANE_API_TOKEN "$hekate_token"
set_env "$ENV_FILE" PLANE_STATUS_FIELD "state"
set_env "$ENV_FILE" PLANE_STATUS_MAP "$status_map"

if [ -f "$BRIDGE_ENV_FILE" ]; then
  # shellcheck disable=SC1090
  source "$BRIDGE_ENV_FILE"
  set_env "$ENV_FILE" OPENCLAW_BASE_URL "http://${OPENCLAW_BRIDGE_HOST}:${OPENCLAW_BRIDGE_PORT}"
  set_env "$ENV_FILE" OPENCLAW_TOKEN "$OPENCLAW_BRIDGE_TOKEN"
fi

set_env "$PLANE_ENV_FILE" AGENTPM_ADMIN_TOKEN "$admin_token"
set_env "$PLANE_ENV_FILE" AGENTPM_INTERNAL_URL "http://agentpm:8080"

echo "Production environment configured without printing secret values."
