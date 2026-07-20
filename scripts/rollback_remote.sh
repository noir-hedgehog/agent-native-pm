#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="${AGENTPM_DEPLOY_HOST:-ubuntu}"
REMOTE_DIR="${AGENTPM_DEPLOY_DIR:-agent-native-pm}"
BACKUP_NAME="${1:-}"

if [ -z "$BACKUP_NAME" ]; then
  echo "Usage: $0 <source-backup.tar.gz>" >&2
  ssh "$REMOTE_HOST" "ls -1t ~/$REMOTE_DIR/.deploy/source-backups/*.tar.gz 2>/dev/null | head -10" || true
  exit 2
fi

ssh "$REMOTE_HOST" "test -f ~/$REMOTE_DIR/.deploy/source-backups/$BACKUP_NAME"
ssh "$REMOTE_HOST" "cd ~/$REMOTE_DIR && tar -xzf .deploy/source-backups/$BACKUP_NAME && sudo docker compose -f docker-compose.agentpm.yml up -d --build"
ssh "$REMOTE_HOST" "curl -fsS http://127.0.0.1:8081/health"
