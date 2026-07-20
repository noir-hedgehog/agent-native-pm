#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

command -v openclaw >/dev/null 2>&1 || { echo "openclaw CLI not found" >&2; exit 1; }
./scripts/seed_plane_mvp.sh >/dev/null
./scripts/seed_plane_agents.sh >/dev/null

SERVER_AGENT_ID="${AGENTPM_MCP_AGENT_ID:-}"
SERVER_NAME="agentpm-plane"
LOCK_ENV=()
if [ -n "$SERVER_AGENT_ID" ]; then
  SERVER_NAME="agentpm-plane-$SERVER_AGENT_ID"
  LOCK_ENV=(--env PLANE_MCP_LOCKED_AGENT_ID="$SERVER_AGENT_ID" --env PLANE_MCP_AGENT_ID="$SERVER_AGENT_ID")
fi

openclaw mcp add "$SERVER_NAME" \
  --command ./scripts/plane_mcp_stdio.sh \
  --cwd "$ROOT_DIR" \
  "${LOCK_ENV[@]}" \
  --timeout 20 \
  --connect-timeout 20 \
  --include 'plane_*'

openclaw mcp reload >/dev/null 2>&1 || true
openclaw mcp probe "$SERVER_NAME" --json
