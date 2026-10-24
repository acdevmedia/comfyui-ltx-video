#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${COMFYUI_DIR:-/workspace/ComfyUI}"
mkdir -p "$ROOT"/{models/{diffusion_models,text_encoders,vae,latent_upscale_models,loras},input,output,user/default/workflows} /workspace/logs /workspace/.cache/huggingface /workspace/.ltx25-studio
chmod 700 /workspace/.ltx25-studio
python /opt/ltx25-studio/scripts/install-workflows.py
cat >/opt/ltx25-studio/config/extra_model_paths.yaml <<EOF
ltx25_workspace:
  base_path: $ROOT
  checkpoints: models/checkpoints/
  loras: models/loras/
  vae: models/vae/
  clip: models/clip/
  clip_vision: models/clip_vision/
  unet: models/unet/
  controlnet: models/controlnet/
  upscale_models: models/upscale_models/
  embeddings: models/embeddings/
  diffusion_models: models/diffusion_models/
  text_encoders: models/text_encoders/
  latent_upscale_models: models/latent_upscale_models/
  input: input/
  output: output/
  temp: temp/
EOF
echo "[startup] Persistent workspace ready at $ROOT"
