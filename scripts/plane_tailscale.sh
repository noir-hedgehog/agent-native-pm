#!/usr/bin/env bash
set -euo pipefail

if ! command -v tailscale >/dev/null 2>&1; then
  echo "tailscale CLI not found" >&2
  exit 1
fi

if ! tailscale status >/dev/null 2>&1; then
  echo "tailscale is not running or is not authenticated" >&2
  exit 1
fi

ip="$(tailscale ip -4 | head -n 1)"
dns="$(tailscale status --json | python3 -c 'import json, sys; print(json.load(sys.stdin).get("Self", {}).get("DNSName", "").rstrip("."))')"

echo "Plane over Tailscale:"
echo "  http://$ip/"
echo "  MCP: http://$ip/api/v1/workspaces/agentpm/mcp/"
if [ -n "$dns" ]; then
  echo "  http://$dns/"
  echo "  MCP: http://$dns/api/v1/workspaces/agentpm/mcp/"
fi

if curl --noproxy '*' -fsS -I --max-time 8 "http://$ip/" >/dev/null; then
  echo "Plane HTTP is reachable on the Tailscale IP."
else
  echo "Plane did not respond on http://$ip/. Is ./scripts/plane_service.sh backend running?" >&2
  exit 1
fi

case "${1:-status}" in
  status)
    tailscale serve status || true
    ;;
  serve)
    echo "Attempting to enable Tailscale Serve for local Plane on port 80..."
    tailscale serve --bg --yes 80
    ;;
  *)
    echo "usage: $0 [status|serve]" >&2
    exit 2
    ;;
esac
