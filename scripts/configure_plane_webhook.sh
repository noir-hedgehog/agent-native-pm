#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env.agentpm"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing $ENV_FILE; run scripts/configure_production_env.sh first." >&2
  exit 2
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

cd "$ROOT_DIR/plane"
sudo docker compose exec -T \
  -e PLANE_WEBHOOK_SECRET="$PLANE_WEBHOOK_SECRET" \
  api python manage.py shell <<'PY'
import os
from plane.db.models import Webhook, Workspace

workspace = Workspace.objects.get(slug="agentpm")
webhook, _ = Webhook.objects.update_or_create(
    workspace=workspace,
    url="http://agentpm:8080/webhooks/plane/assignment",
    defaults={
        "secret_key": os.environ["PLANE_WEBHOOK_SECRET"],
        "is_active": True,
        "issue": True,
        "project": False,
        "module": False,
        "cycle": False,
        "issue_comment": False,
        "is_internal": True,
    },
)
print(f"Configured AgentPM assignment webhook {webhook.id}")
PY
