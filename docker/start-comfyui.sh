#!/usr/bin/env bash
set -Eeuo pipefail
APP=/opt/ltx25-studio/ComfyUI
ROOT="${COMFYUI_DIR:-/workspace/ComfyUI}"
PORT="${COMFYUI_PORT:-8188}"
memory_args=()
# Match the original setup's automatic VRAM budget unless explicitly overridden.
if [[ -n "${COMFYUI_RESERVE_VRAM:-}" ]]; then
  memory_args+=(--reserve-vram "$COMFYUI_RESERVE_VRAM")
fi
attention_args=()
# The entrypoint probes SageAttention and falls back to pytorch when it cannot run.
case "${COMFYUI_ATTENTION:-sage}" in
  sage) attention_args+=(--use-sage-attention) ;;
  pytorch) attention_args+=(--use-pytorch-cross-attention) ;;
  *) echo "Unknown COMFYUI_ATTENTION=${COMFYUI_ATTENTION}; expected sage or pytorch." >&2; exit 2 ;;
esac
exec python "$APP/main.py" --listen 0.0.0.0 --port "$PORT" --input-directory "$ROOT/input" --output-directory "$ROOT/output" --user-directory "$ROOT/user" --extra-model-paths-config /opt/ltx25-studio/config/extra_model_paths.yaml "${memory_args[@]}" "${attention_args[@]}"
