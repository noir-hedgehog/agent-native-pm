#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLANE_DIR="$ROOT_DIR/plane"

set_env() {
  local file="$1" key="$2" value="$3" temp
  temp="$(mktemp)"
  awk -v key="$key" -F= '$1 != key { print }' "$file" > "$temp"
  printf '%s=%s\n' "$key" "$value" >> "$temp"
  chmod 600 "$temp"
  mv "$temp" "$file"
}

for service in "" web api space admin live; do
  if [ -n "$service" ]; then
    example="$PLANE_DIR/apps/$service/.env.example"
    target="$PLANE_DIR/apps/$service/.env"
  else
    example="$PLANE_DIR/.env.example"
    target="$PLANE_DIR/.env"
  fi
  if [ ! -f "$target" ]; then
    cp "$example" "$target"
    chmod 600 "$target"
  fi
done

plane_env="$PLANE_DIR/.env"
api_env="$PLANE_DIR/apps/api/.env"
tail_ip="$(tailscale ip -4 2>/dev/null | head -1 || true)"
listen_host="${PLANE_LISTEN_HOST:-${tail_ip:-127.0.0.1}}"
external_url="${PLANE_EXTERNAL_URL:-http://${listen_host}:8080}"

postgres_password="$(awk -F= '$1 == "POSTGRES_PASSWORD" && $2 !~ /plane/ {gsub(/"/, "", $2); print $2; exit}' "$plane_env")"
rabbit_password="$(awk -F= '$1 == "RABBITMQ_PASSWORD" && $2 !~ /plane/ {gsub(/"/, "", $2); print $2; exit}' "$plane_env")"
minio_secret="$(awk -F= '$1 == "AWS_SECRET_ACCESS_KEY" && $2 !~ /secret-key/ {gsub(/"/, "", $2); print $2; exit}' "$plane_env")"
[ -n "$postgres_password" ] || postgres_password="$(openssl rand -hex 24)"
[ -n "$rabbit_password" ] || rabbit_password="$(openssl rand -hex 24)"
[ -n "$minio_secret" ] || minio_secret="$(openssl rand -hex 24)"

set_env "$plane_env" POSTGRES_PASSWORD "$postgres_password"
set_env "$plane_env" RABBITMQ_PASSWORD "$rabbit_password"
set_env "$plane_env" AWS_SECRET_ACCESS_KEY "$minio_secret"
set_env "$plane_env" LISTEN_HOST "$listen_host"
set_env "$plane_env" LISTEN_HTTP_PORT "8080"
set_env "$plane_env" LISTEN_HTTPS_PORT "8443"
set_env "$plane_env" SITE_ADDRESS ":80"
if [ -n "${PLANE_ALPINE_MIRROR:-}" ]; then
  set_env "$plane_env" ALPINE_MIRROR "$PLANE_ALPINE_MIRROR"
fi
if [ -n "${PLANE_PIP_INDEX_URL:-}" ]; then
  set_env "$plane_env" PIP_INDEX_URL "$PLANE_PIP_INDEX_URL"
fi
if [ -n "${PLANE_NPM_REGISTRY:-}" ]; then
  set_env "$plane_env" NPM_REGISTRY "$PLANE_NPM_REGISTRY"
fi

set_env "$api_env" POSTGRES_PASSWORD "$postgres_password"
set_env "$api_env" RABBITMQ_PASSWORD "$rabbit_password"
set_env "$api_env" AWS_SECRET_ACCESS_KEY "$minio_secret"
set_env "$api_env" AWS_S3_ENDPOINT_URL "http://plane-minio:9000"
set_env "$api_env" USE_MINIO "1"
set_env "$api_env" WEB_URL "$external_url"
set_env "$api_env" APP_BASE_URL "$external_url"
set_env "$api_env" ADMIN_BASE_URL "$external_url"
set_env "$api_env" SPACE_BASE_URL "$external_url"
set_env "$api_env" LIVE_BASE_URL "$external_url"
set_env "$api_env" CORS_ALLOWED_ORIGINS "$external_url"
set_env "$api_env" MESH_ENVIRONMENT "production"
set_env "$api_env" MESH_RUNNER_AUTOSTART "1"

if ! grep -q '^SECRET_KEY=' "$api_env"; then
  set_env "$api_env" SECRET_KEY "$(openssl rand -hex 32)"
fi
if grep -Eq '^LIVE_SERVER_SECRET_KEY="?secret-key"?$' "$api_env"; then
  set_env "$api_env" LIVE_SERVER_SECRET_KEY "$(openssl rand -hex 32)"
fi

echo "Plane production environment is ready at $external_url."
