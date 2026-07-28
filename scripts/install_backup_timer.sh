#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_FILE=/etc/systemd/system/mesh-backup.service
TIMER_FILE=/etc/systemd/system/mesh-backup.timer
BACKUP_ROOT="${MESH_BACKUP_DIR:-$ROOT_DIR/backups}"

sudo tee "$SERVICE_FILE" >/dev/null <<EOF
[Unit]
Description=Back up Mesh PostgreSQL, uploads, registry, and legacy runtime data
After=docker.service

[Service]
Type=oneshot
WorkingDirectory=$ROOT_DIR
Environment=MESH_BACKUP_DIR=$BACKUP_ROOT
ExecStart=$ROOT_DIR/scripts/backup_services.sh
EOF

sudo tee "$TIMER_FILE" >/dev/null <<'EOF'
[Unit]
Description=Daily Mesh production backup

[Timer]
OnCalendar=*-*-* 03:30:00
Persistent=true
RandomizedDelaySec=20m

[Install]
WantedBy=timers.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now mesh-backup.timer
sudo systemctl list-timers mesh-backup.timer --no-pager
