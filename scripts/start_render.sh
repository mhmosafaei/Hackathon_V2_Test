#!/usr/bin/env bash
set -euo pipefail
: "${PERMITPULSE_DATA_DIR:=/var/data}"
mkdir -p "$PERMITPULSE_DATA_DIR/cache"
if [ -L cache ]; then
  [ "$(readlink cache)" = "$PERMITPULSE_DATA_DIR/cache" ] || { echo "Unexpected cache symlink" >&2; exit 1; }
elif [ -e cache ]; then
  echo "Refusing to replace existing cache directory; migrate data before deploying" >&2
  exit 1
else
  ln -s "$PERMITPULSE_DATA_DIR/cache" cache
fi
exec uvicorn src.permit.simple_api:create_app --factory --host 0.0.0.0 --port "${PORT:-10000}" --workers 1 --proxy-headers --forwarded-allow-ips='*'
