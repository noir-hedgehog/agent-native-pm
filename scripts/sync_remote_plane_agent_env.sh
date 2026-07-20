#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE_HOST="${AGENTPM_DEPLOY_HOST:-ubuntu}"
REMOTE_DIR="${AGENTPM_DEPLOY_DIR:-agent-native-pm}"
TARGET="${AGENTPM_REMOTE_AGENT_ENV_FILE:-$ROOT_DIR/.agentpm/plane-agent-env.remote.sh}"

mkdir -p "$(dirname "$TARGET")"
temp="$(mktemp "${TARGET}.XXXXXX")"
trap 'rm -f "$temp"' EXIT
scp -q "$REMOTE_HOST:$REMOTE_DIR/.agentpm/plane-agent-env.sh" "$temp"
chmod 600 "$temp"
mv "$temp" "$TARGET"
trap - EXIT

echo "Synced remote Plane agent credentials to ignored file: $TARGET"
