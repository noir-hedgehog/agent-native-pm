#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/plane"

upstream_ref="${PLANE_UPSTREAM_REF:-origin/preview}"
git fetch --quiet origin preview
base="$(git merge-base HEAD "$upstream_ref")"
behind="$(git rev-list --count HEAD.."$upstream_ref")"
ahead="$(git rev-list --count "$upstream_ref"..HEAD)"

printf 'base=%s\nupstream=%s\nbehind=%s\nahead=%s\n' "$base" "$upstream_ref" "$behind" "$ahead"
git diff --stat "$base".."$upstream_ref"
