#!/usr/bin/env bash
set -Eeuo pipefail
APP=/opt/ltx25-studio/ComfyUI
ROOT="${COMFYUI_DIR:-/workspace/ComfyUI}"
PORT="${COMFYUI_PORT:-8188}"
exec python "$APP/main.py" --listen 0.0.0.0 --port "$PORT" --input-directory "$ROOT/input" --output-directory "$ROOT/output" --user-directory "$ROOT/user" --extra-model-paths-config /opt/ltx25-studio/config/extra_model_paths.yaml --reserve-vram "${COMFYUI_RESERVE_VRAM:-4}"
