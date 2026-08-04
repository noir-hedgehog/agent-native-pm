#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE_HOST="${AGENTPM_DEPLOY_HOST:-ubuntu}"
REMOTE_DIR="${AGENTPM_DEPLOY_DIR:-agent-native-pm}"
REMOTE_ALPINE_MIRROR="${AGENTPM_DEPLOY_ALPINE_MIRROR:-http://mirrors.tencentyun.com/alpine}"
REMOTE_PIP_INDEX_URL="${AGENTPM_DEPLOY_PIP_INDEX_URL:-https://mirrors.cloud.tencent.com/pypi/simple}"
REMOTE_NPM_REGISTRY="${AGENTPM_DEPLOY_NPM_REGISTRY:-https://registry.npmmirror.com}"
DEPLOY_PLANE=0
SEED=0

for arg in "$@"; do
  case "$arg" in
    --plane) DEPLOY_PLANE=1 ;;
    --seed) SEED=1 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

command -v rsync >/dev/null || { echo "rsync is required" >&2; exit 2; }
ssh -o BatchMode=yes "$REMOTE_HOST" true

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
ssh "$REMOTE_HOST" "mkdir -p ~/$REMOTE_DIR/.deploy/source-backups && if [ -d ~/$REMOTE_DIR/src ]; then tar -czf ~/$REMOTE_DIR/.deploy/source-backups/$timestamp.tar.gz -C ~/$REMOTE_DIR --exclude=.agentpm --exclude=.env.agentpm --exclude=.deploy .; fi"

rsync -az --delete \
  --exclude '.git/' \
  --exclude 'plane/.git/' \
  --exclude '.agentpm/' \
  --exclude '.env.agentpm' \
  --include '.env.agentpm.example' \
  --include '**/.env.example' \
  --exclude '**/.env' \
  --exclude '**/.env.*' \
  --exclude '**/node_modules/' \
  --exclude '**/__pycache__/' \
  --exclude '**/.next/' \
  --exclude '**/dist/' \
  "$ROOT_DIR/" "$REMOTE_HOST:$REMOTE_DIR/"

if [ -f "$ROOT_DIR/.agentpm/openclaw-bridge.env" ]; then
  ssh "$REMOTE_HOST" "mkdir -p ~/$REMOTE_DIR/.agentpm && chmod 700 ~/$REMOTE_DIR/.agentpm"
  scp -q "$ROOT_DIR/.agentpm/openclaw-bridge.env" "$REMOTE_HOST:$REMOTE_DIR/.agentpm/openclaw-bridge.env"
  ssh "$REMOTE_HOST" "chmod 600 ~/$REMOTE_DIR/.agentpm/openclaw-bridge.env"
fi

if [ -f "$ROOT_DIR/.agentpm/mesh-agent-gateway.env" ]; then
  ssh "$REMOTE_HOST" "mkdir -p ~/$REMOTE_DIR/.agentpm && chmod 700 ~/$REMOTE_DIR/.agentpm"
  scp -q "$ROOT_DIR/.agentpm/mesh-agent-gateway.env" "$REMOTE_HOST:$REMOTE_DIR/.agentpm/mesh-agent-gateway.env"
  ssh "$REMOTE_HOST" "chmod 600 ~/$REMOTE_DIR/.agentpm/mesh-agent-gateway.env"
fi

ssh "$REMOTE_HOST" "cd ~/$REMOTE_DIR && PLANE_ALPINE_MIRROR='$REMOTE_ALPINE_MIRROR' PLANE_PIP_INDEX_URL='$REMOTE_PIP_INDEX_URL' PLANE_NPM_REGISTRY='$REMOTE_NPM_REGISTRY' ./scripts/prepare_plane_production_env.sh"

if [ "$DEPLOY_PLANE" -eq 1 ]; then
  ssh "$REMOTE_HOST" "cd ~/$REMOTE_DIR/plane && sudo docker compose up -d --build"
fi

if [ "$SEED" -eq 1 ]; then
  ssh "$REMOTE_HOST" "cd ~/$REMOTE_DIR && mkdir -p .agentpm && chmod 700 .agentpm && ./scripts/seed_plane_mvp.sh > .agentpm/plane-seed-env.sh && chmod 600 .agentpm/plane-seed-env.sh && ./scripts/seed_plane_agents.sh && ./scripts/seed_plane_agent_guide_page.sh"
fi

ssh "$REMOTE_HOST" "cd ~/$REMOTE_DIR && ./scripts/configure_production_env.sh"
ssh "$REMOTE_HOST" "cd ~/$REMOTE_DIR/plane && sudo docker compose up -d api"
ssh "$REMOTE_HOST" "cd ~/$REMOTE_DIR && sudo docker compose -f docker-compose.agentpm.yml up -d --build"
ssh "$REMOTE_HOST" "cd ~/$REMOTE_DIR && ./scripts/configure_plane_webhook.sh"
ssh "$REMOTE_HOST" "cd ~/$REMOTE_DIR && ./scripts/install_backup_timer.sh"

ssh "$REMOTE_HOST" "curl -fsS http://127.0.0.1:8081/health"
printf '\nDeployment complete: %s:%s\n' "$REMOTE_HOST" "$REMOTE_DIR"
