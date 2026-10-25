#!/usr/bin/env bash
set -Eeuo pipefail
APP_ROOT="${LTX_STUDIO_ROOT:-/opt/ltx25-studio}"
if [[ ! -f "$APP_ROOT/scripts/download-models.py" ]]; then APP_ROOT="$(cd "$(dirname "$0")/.." && pwd)"; fi
exec python "$APP_ROOT/scripts/download-models.py" --group ingredients
