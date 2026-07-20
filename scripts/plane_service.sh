#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLANE_DIR="${PLANE_DIR:-$ROOT_DIR/plane}"

usage() {
  cat <<'EOF'
Usage: scripts/plane_service.sh <up|backend|down|status|logs>

Commands:
  up       Start the full Plane compose stack from ./plane/docker-compose.yml.
  backend  Start backend dependencies/API from ./plane/docker-compose.yml.
  down     Stop both known Plane compose stacks.
  status   Show container status for both known Plane compose stacks.
  logs     Follow logs for the active Plane compose services.

Environment:
  PLANE_DIR  Path to a local Plane checkout. Defaults to ./plane.
EOF
}

require_plane_dir() {
  if [ ! -d "$PLANE_DIR" ]; then
    echo "Plane checkout not found at $PLANE_DIR" >&2
    echo "Set PLANE_DIR or clone Plane into ./plane." >&2
    exit 1
  fi
}

ensure_local_env() {
  "$ROOT_DIR/scripts/init_mesh_console_env.sh"
}

backend_is_running() {
  local container
  for container in plane-db plane-redis plane-mq plane-minio api bgworker beatworker mesh-runner mesh-indexer; do
    if [ "$(docker inspect -f '{{.State.Running}}' "$container" 2>/dev/null || true)" != "true" ]; then
      return 1
    fi
  done
}

compose() {
  docker compose "$@"
}

cmd="${1:-}"
case "$cmd" in
  up)
    require_plane_dir
    ensure_local_env
    cd "$PLANE_DIR"
    compose -f docker-compose.yml up -d
    ;;
  backend)
    require_plane_dir
    ensure_local_env
    if backend_is_running; then
      echo "Mesh Console backend is already running."
      exit 0
    fi
    cd "$PLANE_DIR"
    compose -f docker-compose.yml up -d plane-db plane-redis plane-mq plane-minio migrator api worker beat-worker
    ;;
  down)
    require_plane_dir
    cd "$PLANE_DIR"
    compose -f docker-compose-local.yml down || true
    compose -f docker-compose.yml down || true
    ;;
  status)
    require_plane_dir
    cd "$PLANE_DIR"
    echo "== docker-compose-local.yml =="
    compose -f docker-compose-local.yml ps || true
    echo "== docker-compose.yml =="
    compose -f docker-compose.yml ps || true
    ;;
  logs)
    require_plane_dir
    cd "$PLANE_DIR"
    if compose -f docker-compose.yml ps --services --filter status=running | grep -q .; then
      compose -f docker-compose.yml logs -f
    else
      compose -f docker-compose-local.yml logs -f
    fi
    ;;
  -h|--help|help|"")
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
