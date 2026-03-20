#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8080}"
SECRET="${PLANE_WEBHOOK_SECRET:-dev-secret}"

PYTHONPATH=src PLANE_WEBHOOK_SECRET="$SECRET" PORT="$PORT" python3 -m agentpm.server > /tmp/agentpm-server.log 2>&1 &
SERVER_PID=$!

cleanup() {
  kill "$SERVER_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT

for _ in {1..30}; do
  if curl -s "http://127.0.0.1:$PORT/metrics/projects/proj_local" >/dev/null 2>&1; then
    break
  fi
  sleep 0.2
done

echo "[1/3] sending signed webhook"
python3 scripts/send_signed_assignment.py \
  --url "http://127.0.0.1:$PORT/webhooks/plane/assignment" \
  --secret "$SECRET" \
  --event-id "plane_evt_local_001" \
  --task-id "task_local_001" \
  --project-id "proj_local"

echo "[2/3] querying metrics"
curl -s "http://127.0.0.1:$PORT/metrics/projects/proj_local" | sed 's/.*/&/'

echo "[3/3] querying timeline"
curl -s "http://127.0.0.1:$PORT/tasks/task_local_001/timeline" | sed 's/.*/&/'

echo "Smoke test complete. Server log: /tmp/agentpm-server.log"
