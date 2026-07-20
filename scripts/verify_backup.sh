#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-}"
if [ -z "$TARGET" ] || [ ! -d "$TARGET" ]; then
  echo "Usage: $0 <backup-directory>" >&2
  exit 2
fi

(cd "$TARGET" && sha256sum -c SHA256SUMS)
gzip -t "$TARGET/plane-postgres.sql.gz"
for archive in "$TARGET"/*.tar.gz; do
  tar -tzf "$archive" >/dev/null
done
echo "Backup checksums and archives are valid: $TARGET"
