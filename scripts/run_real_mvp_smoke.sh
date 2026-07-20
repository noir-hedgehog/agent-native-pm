#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PORT="${PORT:-18280}"
SECRET="${PLANE_WEBHOOK_SECRET:-dev-secret}"
PROVIDER="${AGENTPM_AGENT_PROVIDER:-}"
TASK_ID="${REAL_TASK_ID:-}"
PROJECT_ID="${REAL_PROJECT_ID:-}"
ASSIGNEE="${REAL_AGENT_ASSIGNEE:-agent_${PROVIDER:-provider}_default}"

require_env() {
  local name="$1"
  if [ -z "${!name:-}" ]; then
    echo "Missing required environment variable: $name" >&2
    exit 2
  fi
}

case "$PROVIDER" in
  openclaw)
    require_env OPENCLAW_BASE_URL
    ;;
  hermes)
    require_env HERMES_BASE_URL
    ;;
  *)
    echo "Set AGENTPM_AGENT_PROVIDER to openclaw or hermes for real MVP smoke." >&2
    exit 2
    ;;
esac

require_env REAL_TASK_ID
require_env REAL_PROJECT_ID
require_env PLANE_API_BASE_URL
require_env PLANE_WORKSPACE_SLUG
require_env PLANE_API_TOKEN

PYTHONPATH=src \
PLANE_WEBHOOK_SECRET="$SECRET" \
PORT="$PORT" \
python3 -m agentpm.server > "/tmp/agentpm-real-${PROVIDER}-server.log" 2>&1 &
SERVER_PID=$!

cleanup() {
  kill "$SERVER_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT

ready=0
for _ in {1..50}; do
  if curl -sf "http://127.0.0.1:$PORT/metrics/projects/$PROJECT_ID" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 0.2
done

if [ "$ready" -ne 1 ]; then
  echo "AgentPM server did not become ready. Check /tmp/agentpm-real-${PROVIDER}-server.log" >&2
  exit 1
fi

event_id="plane_evt_real_${PROVIDER}_$(date +%s)"

echo "[1/3] sending real signed assignment webhook via $PROVIDER"
python3 scripts/send_signed_assignment.py \
  --url "http://127.0.0.1:$PORT/webhooks/plane/assignment" \
  --secret "$SECRET" \
  --event-id "$event_id" \
  --task-id "$TASK_ID" \
  --project-id "$PROJECT_ID" \
  --assignee "$ASSIGNEE"

echo "[2/3] querying real task timeline"
timeline="$(curl -s "http://127.0.0.1:$PORT/tasks/$TASK_ID/timeline")"
echo "$timeline"

echo "[3/3] validating real MVP lifecycle"
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
if not started["payload"].get("provider_run_id"):
    raise SystemExit("provider_run_id missing from started event")
'

echo "Real MVP smoke complete for $PROVIDER."
echo "Server log: /tmp/agentpm-real-${PROVIDER}-server.log"
