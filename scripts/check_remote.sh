#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="${AGENTPM_DEPLOY_HOST:-ubuntu}"
REMOTE_DIR="${AGENTPM_DEPLOY_DIR:-agent-native-pm}"

ssh "$REMOTE_HOST" "cd ~/$REMOTE_DIR/plane && sudo docker compose ps"
ssh "$REMOTE_HOST" "cd ~/$REMOTE_DIR && sudo docker compose -f docker-compose.agentpm.yml ps"
ssh "$REMOTE_HOST" "curl -fsS http://127.0.0.1:8081/health"
printf '\n'
