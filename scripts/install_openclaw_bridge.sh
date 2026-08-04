#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "install_openclaw_bridge.sh is deprecated; installing the A2A 1.0 Mesh Agent Gateway." >&2
exec "$ROOT_DIR/scripts/install_mesh_agent_gateway.sh" "$@"

: <<'LEGACY_OPENCLAW_BRIDGE'

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.agentpm/openclaw-bridge.env"
INSTALL_DIR="$HOME/.agentpm/openclaw-bridge"
RUNTIME_ENV_FILE="$INSTALL_DIR/openclaw-bridge.env"
RUNTIME_SCRIPT="$INSTALL_DIR/openclaw_bridge.py"
PLIST="$HOME/Library/LaunchAgents/dev.agentpm.openclaw-bridge.plist"
mkdir -p "$ROOT_DIR/.agentpm" "$INSTALL_DIR/runs" "$HOME/Library/LaunchAgents"

if [ ! -f "$ENV_FILE" ]; then
  token="$(openssl rand -hex 32)"
  bridge_host="$(tailscale ip -4 | head -1)"
  {
    printf 'export OPENCLAW_BRIDGE_TOKEN=%q\n' "$token"
    printf 'export OPENCLAW_BRIDGE_HOST=%q\n' "$bridge_host"
    printf 'export OPENCLAW_BRIDGE_PORT=18890\n'
    printf 'export OPENCLAW_BRIDGE_DEFAULT_AGENT=hekate\n'
    printf 'export OPENCLAW_BRIDGE_ROLE_MAP=%q\n' '{"coder":"iris","tester":"lingxi","reviewer":"hekate"}'
    printf 'export OPENCLAW_BRIDGE_STATE_DIR=%q\n' "$INSTALL_DIR/runs"
    printf 'export OPENCLAW_BIN=/opt/homebrew/bin/openclaw\n'
  } > "$ENV_FILE"
fi

temp_env="$(mktemp)"
awk -F= '$1 != "export OPENCLAW_BRIDGE_STATE_DIR" { print }' "$ENV_FILE" > "$temp_env"
printf 'export OPENCLAW_BRIDGE_STATE_DIR=%q\n' "$INSTALL_DIR/runs" >> "$temp_env"
mv "$temp_env" "$ENV_FILE"
chmod 600 "$ENV_FILE"

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

cp "$ROOT_DIR/scripts/openclaw_bridge.py" "$RUNTIME_SCRIPT"
cp "$ENV_FILE" "$RUNTIME_ENV_FILE"
chmod 600 "$RUNTIME_ENV_FILE" "$RUNTIME_SCRIPT"

python3 - <<PY
from pathlib import Path
path = Path("$PLIST")
path.write_text('''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>dev.agentpm.openclaw-bridge</string>
<key>ProgramArguments</key><array><string>/usr/bin/env</string><string>bash</string><string>-lc</string><string>source "$RUNTIME_ENV_FILE"; exec python3 "$RUNTIME_SCRIPT"</string></array>
<key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
<key>WorkingDirectory</key><string>$INSTALL_DIR</string>
<key>StandardOutPath</key><string>/tmp/agentpm-openclaw-bridge.log</string>
<key>StandardErrorPath</key><string>/tmp/agentpm-openclaw-bridge.err.log</string>
</dict></plist>''', encoding="utf-8")
PY

launchctl bootout "gui/$UID/dev.agentpm.openclaw-bridge" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$UID" "$PLIST"
launchctl kickstart -k "gui/$UID/dev.agentpm.openclaw-bridge"
for _ in {1..30}; do
  if curl --noproxy '*' -fsS "http://$OPENCLAW_BRIDGE_HOST:$OPENCLAW_BRIDGE_PORT/health"; then
    break
  fi
  sleep 0.5
done
curl --noproxy '*' -fsS "http://$OPENCLAW_BRIDGE_HOST:$OPENCLAW_BRIDGE_PORT/health" >/dev/null
printf '\nBridge installed at http://%s:%s\n' "$OPENCLAW_BRIDGE_HOST" "$OPENCLAW_BRIDGE_PORT"
LEGACY_OPENCLAW_BRIDGE
