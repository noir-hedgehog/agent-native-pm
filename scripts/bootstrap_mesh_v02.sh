#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_CONTAINER="${MESH_API_CONTAINER:-api}"
CONTAINER_SCRIPT="/tmp/bootstrap_mesh_v02.py"
DOCKER=(docker)

if ! docker info >/dev/null 2>&1; then
  DOCKER=(sudo docker)
fi

"${DOCKER[@]}" cp "$ROOT_DIR/scripts/bootstrap_mesh_v02.py" "$API_CONTAINER:$CONTAINER_SCRIPT"
"${DOCKER[@]}" exec \
  -e MESH_V02_PROJECT_IDENTIFIER="${MESH_V02_PROJECT_IDENTIFIER:-AGPM}" \
  -e MESH_V02_GATEWAY_BASE_URL="${MESH_V02_GATEWAY_BASE_URL:-}" \
  -e MESH_V02_SYNC_AGENT_CARDS="${MESH_V02_SYNC_AGENT_CARDS:-0}" \
  "$API_CONTAINER" python manage.py shell -c "exec(open('$CONTAINER_SCRIPT').read())"
