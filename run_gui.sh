#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PORT="${1:-8000}"
URL="http://127.0.0.1:${PORT}/viewer/viewer.html"
echo "idxpaint GUI: ${URL}"
if command -v xdg-open >/dev/null 2>&1; then
  (sleep 1; xdg-open "${URL}" >/dev/null 2>&1 || true) &
fi
exec python3 -m http.server "${PORT}" --bind 127.0.0.1
