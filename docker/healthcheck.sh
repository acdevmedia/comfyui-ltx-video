#!/usr/bin/env bash
set -eu
port="${COMFYUI_PORT:-8188}"
python - "$port" <<'PY'
import json, sys, urllib.request
try:
    with urllib.request.urlopen(f"http://127.0.0.1:{sys.argv[1]}/system_stats", timeout=3) as r: data=json.load(r)
    if not data.get("system", {}).get("comfyui_version"): raise SystemExit(1)
except Exception: raise SystemExit(1)
PY
