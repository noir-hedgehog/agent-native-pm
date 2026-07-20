#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_FILE=/etc/systemd/system/agentpm-backup.service
TIMER_FILE=/etc/systemd/system/agentpm-backup.timer

sudo tee "$SERVICE_FILE" >/dev/null <<EOF
[Unit]
Description=Back up Plane and AgentPM data
After=docker.service

[Service]
Type=oneshot
WorkingDirectory=$ROOT_DIR
ExecStart=$ROOT_DIR/scripts/backup_services.sh
EOF

sudo tee "$TIMER_FILE" >/dev/null <<'EOF'
[Unit]
Description=Daily Plane and AgentPM backup

[Timer]
OnCalendar=*-*-* 03:30:00
Persistent=true
RandomizedDelaySec=20m

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now agentpm-backup.timer
sudo systemctl list-timers agentpm-backup.timer --no-pager
