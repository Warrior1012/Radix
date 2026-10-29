#!/usr/bin/env bash
# Usage: ./snapshot.sh <phase-number>   -> /mnt/user-data/outputs/radix-talent-match-phase<N>.zip
set -e
cd "$(dirname "$0")/.."
mkdir -p /mnt/user-data/outputs
rm -f /mnt/user-data/outputs/radix-talent-match-phase$1.zip
zip -qr /mnt/user-data/outputs/radix-talent-match-phase$1.zip radix \
  -x '*/data/profiles/*' '*/data/jds/*' '*/.env' '*/.venv/*' '*/node_modules/*' '*/__pycache__/*' '*/dist/*' '*/.pytest_cache/*' '*.pyc'
ls -la /mnt/user-data/outputs/radix-talent-match-phase$1.zip
