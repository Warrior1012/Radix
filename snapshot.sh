#!/usr/bin/env bash
# Build a source-only ZIP for sharing/review. Run with: bash snapshot.sh [output.zip]
# Keep local secrets and generated data out of distributable snapshots.
set -euo pipefail

output="${1:-radix-source-snapshot.zip}"
if [[ "$output" != /* ]]; then
  output="$PWD/$output"
fi
root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# zip's exclusion patterns are intentionally quoted: '*/.env' excludes nested
# environment files as well as other local-only and generated content.
(
  cd "$root"
  zip -qr "$output" . \
    -x '.git/*' '*/.git/*' \
       '.env' '*/.env' 'backend/.env' \
       '.venv/*' '*/.venv/*' \
       'node_modules/*' '*/node_modules/*' \
       '*/__pycache__/*' '*/.pytest_cache/*' \
       'frontend/dist/*' '*/dist/*' \
       'backend/data/jds/*' 'backend/data/profiles/*' \
       'backend/data/jd_extraction_cache.json' \
       'backend/eval/reports/latest.json' \
       "$output"
)
echo "Created source snapshot: $output"
