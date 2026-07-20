#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

eval "$("./scripts/seed_plane_mvp.sh" | /usr/bin/grep '^export ')"
eval "$("./scripts/seed_plane_agents.sh" | /usr/bin/grep '^export ')"

if [ -f "${AGENTPM_PLANE_AGENT_ENV_FILE:-$ROOT_DIR/.agentpm/plane-agent-env.sh}" ]; then
  set -a
  # shellcheck disable=SC1090
  source "${AGENTPM_PLANE_AGENT_ENV_FILE:-$ROOT_DIR/.agentpm/plane-agent-env.sh}"
  set +a
fi

exec python3 scripts/plane_mcp_server.py
