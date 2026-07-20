#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLANE_DIR="${PLANE_DIR:-$ROOT_DIR/plane}"

copy_if_missing() {
  local source="$1"
  local target="$2"
  if [ ! -f "$target" ]; then
    cp "$source" "$target"
    echo "Created ${target#$ROOT_DIR/} from its local development template."
  fi
}

copy_if_missing "$PLANE_DIR/.env.example" "$PLANE_DIR/.env"
for app in api live; do
  copy_if_missing "$PLANE_DIR/apps/$app/.env.example" "$PLANE_DIR/apps/$app/.env"
done

cat <<'EOF'
Mesh Console environment is ready for local development.
Before a shared or production deployment, replace every example password and secret in these ignored .env files.
Frontend production builds intentionally use same-origin API paths; use app-specific .env files only for local frontend dev.
EOF
