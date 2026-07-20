#!/usr/bin/env bash
set -euo pipefail

PROVIDER="${1:-openclaw}"
if [ "$PROVIDER" != "openclaw" ] && [ "$PROVIDER" != "hermes" ]; then
  echo "Usage: scripts/run_plane_writeback_smoke.sh <openclaw|hermes>" >&2
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

./scripts/plane_service.sh backend >/tmp/agentpm-plane-writeback-plane.log 2>&1

MOCK_PORT="${MOCK_AGENT_PROVIDER_PORT:-19190}"
BASE_URL="http://127.0.0.1:$MOCK_PORT"
PYTHONPATH=src MOCK_AGENT_PROVIDER_PORT="$MOCK_PORT" python3 scripts/mock_agent_provider.py > /tmp/agentpm-plane-writeback-mock.log 2>&1 &
MOCK_PID=$!

cleanup() {
  kill "$MOCK_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT

for _ in {1..50}; do
  if curl -sf "$BASE_URL/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.2
done

if ! curl -sf "$BASE_URL/health" >/dev/null 2>&1; then
  echo "Mock provider did not become ready. Check /tmp/agentpm-plane-writeback-mock.log" >&2
  exit 1
fi

seed_env="$(./scripts/seed_plane_mvp.sh)"
eval "$seed_env"
echo "Seeded workspace=$PLANE_WORKSPACE_SLUG project=$REAL_PROJECT_ID work_item=$REAL_TASK_ID (token redacted)"

if [ "$PROVIDER" = "openclaw" ]; then
  export AGENTPM_AGENT_PROVIDER=openclaw
  export OPENCLAW_BASE_URL="$BASE_URL"
else
  export AGENTPM_AGENT_PROVIDER=hermes
  export HERMES_BASE_URL="$BASE_URL"
fi

./scripts/run_real_mvp_smoke.sh

echo "[verify] Plane comments for seeded work item"
curl -sf \
  -H "X-Api-Key: $PLANE_API_TOKEN" \
  "$PLANE_API_BASE_URL/api/v1/workspaces/$PLANE_WORKSPACE_SLUG/projects/$REAL_PROJECT_ID/work-items/$REAL_TASK_ID/comments/" \
  | python3 -c '
import json
import sys

data = json.loads(sys.stdin.read())
items = data.get("results", data if isinstance(data, list) else [])
if not items:
    raise SystemExit("no Plane comments found for seeded work item")
text = json.dumps(items)
if "Stage Completed" not in text:
    raise SystemExit("AgentPM completion comment not found in Plane comments")
print("Plane comment write-back verified.")
'

echo "Plane write-back smoke complete for $PROVIDER."
