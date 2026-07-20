#!/usr/bin/env bash
set -euo pipefail

PROVIDER="${1:-openclaw}"
if [ "$PROVIDER" != "openclaw" ] && [ "$PROVIDER" != "hermes" ]; then
  echo "Usage: scripts/run_connector_smoke.sh <openclaw|hermes>" >&2
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-18180}"
MOCK_PORT="${MOCK_AGENT_PROVIDER_PORT:-19090}"
SECRET="${PLANE_WEBHOOK_SECRET:-dev-secret}"
BASE_URL="http://127.0.0.1:$MOCK_PORT"

cd "$ROOT_DIR"

PYTHONPATH=src MOCK_AGENT_PROVIDER_PORT="$MOCK_PORT" python3 scripts/mock_agent_provider.py > /tmp/agentpm-mock-provider.log 2>&1 &
MOCK_PID=$!

cleanup() {
  kill "$SERVER_PID" >/dev/null 2>&1 || true
  kill "$MOCK_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT

ready=0
for _ in {1..50}; do
  if curl -sf "$BASE_URL/health" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 0.2
done

if [ "$ready" -ne 1 ]; then
  echo "Mock provider did not become ready. Check /tmp/agentpm-mock-provider.log" >&2
  exit 1
fi

if [ "$PROVIDER" = "openclaw" ]; then
  AGENT_ENV=(AGENTPM_AGENT_PROVIDER=openclaw OPENCLAW_BASE_URL="$BASE_URL")
else
  AGENT_ENV=(AGENTPM_AGENT_PROVIDER=hermes HERMES_BASE_URL="$BASE_URL")
fi

env PYTHONPATH=src PLANE_WEBHOOK_SECRET="$SECRET" PORT="$PORT" "${AGENT_ENV[@]}" \
  python3 -m agentpm.server > "/tmp/agentpm-${PROVIDER}-server.log" 2>&1 &
SERVER_PID=$!

ready=0
for _ in {1..50}; do
  if curl -sf "http://127.0.0.1:$PORT/metrics/projects/proj_local" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 0.2
done

if [ "$ready" -ne 1 ]; then
  echo "AgentPM server did not become ready. Check /tmp/agentpm-${PROVIDER}-server.log" >&2
  exit 1
fi

echo "[1/3] sending signed webhook through $PROVIDER connector"
python3 scripts/send_signed_assignment.py \
  --url "http://127.0.0.1:$PORT/webhooks/plane/assignment" \
  --secret "$SECRET" \
  --event-id "plane_evt_${PROVIDER}_001" \
  --task-id "task_${PROVIDER}_001" \
  --project-id "proj_local"

echo "[2/3] querying timeline"
timeline="$(curl -s "http://127.0.0.1:$PORT/tasks/task_${PROVIDER}_001/timeline")"
echo "$timeline"

echo "[3/3] validating connector lifecycle"
printf '%s' "$timeline" | python3 -c '
import json
import sys

timeline = json.loads(sys.stdin.read())
types = [event["event_type"] for event in timeline["events"]]
required = {"webhook.assignment.accepted", "agent_run.created", "agent_run.started", "agent_run.completed"}
missing = sorted(required - set(types))
if missing:
    raise SystemExit(f"missing events: {missing}")
started = next(event for event in timeline["events"] if event["event_type"] == "agent_run.started")
provider_run_id = started["payload"].get("provider_run_id", "")
if not provider_run_id.startswith("mock_run_"):
    raise SystemExit(f"unexpected provider_run_id: {provider_run_id}")
'

echo "Connector smoke complete for $PROVIDER."
