#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

step() {
  printf '\n== %s ==\n' "$1"
}

require_cmd curl
require_cmd python3
require_cmd docker

step "Plane service"
if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon is not running. Start Docker Desktop, then rerun this script." >&2
  exit 1
fi

./scripts/plane_service.sh backend
for _ in {1..60}; do
  if curl -sf http://127.0.0.1:8000/ >/tmp/agentpm-plane-api-health; then
    break
  fi
  sleep 2
done
if ! curl -sf http://127.0.0.1:8000/ >/tmp/agentpm-plane-api-health; then
  echo "Plane API did not become healthy at http://127.0.0.1:8000/." >&2
  ./scripts/plane_service.sh logs >&2 || true
  exit 1
fi
cat /tmp/agentpm-plane-api-health
printf '\n'

if curl -sf http://127.0.0.1/ >/tmp/agentpm-plane-web-health; then
  echo "Plane web is responding at http://127.0.0.1/"
else
  echo "Plane API is healthy; Plane web/proxy is not responding on http://127.0.0.1/." >&2
fi

step "Python tests"
PYTHONPATH=src python3 -m unittest discover -s tests -v

step "AgentPM local smoke"
./scripts/run_local_smoke.sh

step "OpenClaw connector smoke"
./scripts/run_connector_smoke.sh openclaw

step "Hermes connector smoke"
./scripts/run_connector_smoke.sh hermes

step "OpenClaw connector with real Plane write-back"
./scripts/run_plane_writeback_smoke.sh openclaw

step "Hermes connector with real Plane write-back"
./scripts/run_plane_writeback_smoke.sh hermes

step "MVP verification complete"
echo "Plane API, AgentPM dev path, OpenClaw/Hermes connector paths, and real Plane write-back verified."
