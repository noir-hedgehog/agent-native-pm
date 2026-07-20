#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_SRC="$ROOT_DIR/skills/agentpm-plane-workflow"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
CODEX_DEST="$CODEX_HOME/skills/agentpm-plane-workflow"
DRY_RUN=0
INSTALL_CODEX=1
INSTALL_OPENCLAW=1

usage() {
  cat <<'EOF'
Usage: scripts/install_plane_agent_skill.sh [--dry-run] [--codex-only|--openclaw-only]

Installs the AgentPM Plane workflow skill for Codex and OpenClaw.
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      ;;
    --codex-only)
      INSTALL_OPENCLAW=0
      ;;
    --openclaw-only)
      INSTALL_CODEX=0
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

if [ ! -f "$SKILL_SRC/SKILL.md" ]; then
  echo "missing skill source: $SKILL_SRC/SKILL.md" >&2
  exit 1
fi

if [ "$DRY_RUN" -eq 1 ]; then
  if [ "$INSTALL_CODEX" -eq 1 ]; then
    echo "rm -rf '$CODEX_DEST' && mkdir -p '$(dirname "$CODEX_DEST")' && cp -R '$SKILL_SRC' '$CODEX_DEST'"
  fi
  if [ "$INSTALL_OPENCLAW" -eq 1 ]; then
    echo "openclaw skills install '$SKILL_SRC' --as agentpm-plane-workflow --global --force"
  fi
  exit 0
fi

if [ "$INSTALL_CODEX" -eq 1 ]; then
  mkdir -p "$(dirname "$CODEX_DEST")"
  rm -rf "$CODEX_DEST"
  cp -R "$SKILL_SRC" "$CODEX_DEST"
  echo "Installed Codex skill: $CODEX_DEST"
fi

if [ "$INSTALL_OPENCLAW" -eq 1 ]; then
  if ! command -v openclaw >/dev/null 2>&1; then
    echo "openclaw CLI not found; skipped OpenClaw skill install" >&2
    exit 1
  fi
  openclaw skills install "$SKILL_SRC" --as agentpm-plane-workflow --global --force
  echo "Installed OpenClaw skill: agentpm-plane-workflow"
fi
