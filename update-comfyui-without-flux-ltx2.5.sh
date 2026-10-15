#!/usr/bin/env bash
# Official LTX-2.5 Distilled INT8 ConvRot for RunPod ComfyUI Without Flux.
# For an NVIDIA A100 80 GB. Re-runnable; doesn't delete existing model files.
set -Eeuo pipefail

COMFY="${COMFY:-/workspace/ComfyUI}"
PY="${PY:-/opt/venv/bin/python}"
HF="/opt/venv/bin/hf"
COMMIT="06c67806"  # Known working ComfyUI v0.39.0 revision.
LOG="/workspace/ltx25-setup.log"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
fail() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }
trap 'echo "FAILED near line $LINENO. Review $LOG for details." >&2' ERR

mkdir -p /workspace
exec > >(tee -a "$LOG") 2>&1

say 'Checking template and GPU'
[[ -d "$COMFY/.git" ]] || fail "ComfyUI Git checkout not found at $COMFY"
[[ -x "$PY" ]] || fail "Python not found at $PY"
command -v git >/dev/null || fail 'git not installed'
command -v curl >/dev/null || fail 'curl not installed'
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || true
else
  echo 'WARNING: nvidia-smi unavailable. Check that your pod has GPU access.'
fi
"$PY" -c 'import torch; print("PyTorch:", torch.__version__, "CUDA:", torch.version.cuda, "GPU available:", torch.cuda.is_available())'

say 'Updating ComfyUI to known LTX-2.5-compatible revision'
cd "$COMFY"
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  fail 'Tracked ComfyUI files have local changes. Resolve them first; refusing to overwrite.'
fi
git fetch origin
git checkout --detach "$COMMIT"
echo "ComfyUI revision: $(git describe --tags --always)"

say 'Installing ComfyUI dependencies without replacing RunPod PyTorch'
# Do not upgrade torch, torchvision or torchaudio as a deliberate setup step.
grep -Ev '^[[:space:]]*(torch|torchvision|torchaudio)([=<>!~ ;]|$)' requirements.txt > /tmp/ltx25-core-requirements.txt
"$PY" -m pip install -r /tmp/ltx25-core-requirements.txt
"$PY" -m pip install 'comfy-aimdo==0.5.6' 'comfy-kitchen==0.2.37' 'av==17.0.0' 'huggingface_hub>=0.30'
# PyAV 17 can conflict with aiortc<17 on this template; regular ComfyUI video output still works.
"$PY" -c 'from av.video.reformatter import ColorPrimaries; import comfy_aimdo, comfy_kitchen; print("Core imports OK")' 2>/dev/null || echo 'WARNING: Optional import check failed; server startup will be authoritative.'

say 'Checking Hugging Face authentication'
if [[ ! -x "$HF" ]]; then
  fail "hf CLI missing at $HF"
fi
if ! "$HF" auth whoami; then
  echo 'Log in with a READ token whose account has accepted the LTX-2.5 licence:'
  "$HF" auth login
  "$HF" auth whoami || fail 'Hugging Face login failed'
fi

say 'Checking disk space'
df -h "$COMFY"
FREE_KB=$(df -Pk "$COMFY" | awk 'NR==2 {print $4}')
if (( FREE_KB < 30 * 1024 * 1024 )); then
  echo 'WARNING: Less than 30 GiB available. Official models may not fit.'
  echo 'Stopping before downloading. Increase storage or remove unneeded old checkpoints.'
  exit 1
fi

say 'Downloading official LTX-2.5 INT8 distilled model set'
# hf download --local-dir stores files in the matching ComfyUI model directories.
# All LTX weights are from the official gated repo; prompt enhancer is from Comfy-Org.
mkdir -p "$COMFY/models"/{diffusion_models,text_encoders,vae,latent_upscale_models}

fetch() {
  local repo="$1" remote="$2" target="$COMFY/models/$2"
  if [[ -s "$target" ]]; then
    echo "Already present: $target"
    return
  fi
  echo "Downloading $repo / $remote"
  "$HF" download "$repo" "$remote" --local-dir "$COMFY/models"
  [[ -s "$target" ]] || fail "Download missing or empty: $target"
}

fetch Lightricks/LTX-2.5 diffusion_models/ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors
fetch Lightricks/LTX-2.5 text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors
fetch Lightricks/LTX-2.5 vae/ltx-2.5-video-vae-conv-bf16.safetensors
fetch Lightricks/LTX-2.5 vae/ltx-2.5-video-vae-bf16.safetensors
fetch Lightricks/LTX-2.5 vae/ltx-2.5-audio-vae-bf16.safetensors
fetch Lightricks/LTX-2.5 latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors
fetch Comfy-Org/gemma-4 text_encoders/gemma4_e2b_it_int8_convrot.safetensors

say 'Verifying required model files and space'
for f in \
  diffusion_models/ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors \
  text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors \
  vae/ltx-2.5-video-vae-conv-bf16.safetensors \
  vae/ltx-2.5-video-vae-bf16.safetensors \
  vae/ltx-2.5-audio-vae-bf16.safetensors \
  latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors \
  text_encoders/gemma4_e2b_it_int8_convrot.safetensors; do
  [[ -s "$COMFY/models/$f" ]] || fail "Missing: $f"
  ls -lh "$COMFY/models/$f"
done
df -h "$COMFY"

say 'Starting or checking ComfyUI at port 8188'
if curl -fsS --max-time 5 http://127.0.0.1:8188/system_stats >/dev/null 2>&1; then
  echo 'ComfyUI is already running. Restart it using your RunPod template controls to load any updated core/dependencies.'
else
  cd "$COMFY"
  nohup "$PY" main.py --listen 0.0.0.0 --port 8188 > /workspace/comfyui.log 2>&1 < /dev/null &
  echo "Launched ComfyUI PID $! (log /workspace/comfyui.log)"
  READY=0
  for i in $(seq 1 120); do
    if curl -fsS --max-time 3 http://127.0.0.1:8188/system_stats >/dev/null 2>&1; then READY=1; break; fi
    sleep 2
  done
  if (( READY == 0 )); then
    tail -n 100 /workspace/comfyui.log || true
    fail 'ComfyUI did not become available on port 8188'
  fi
  echo 'ComfyUI is ONLINE.'
fi

say 'Complete'
echo 'Open the current pod Connect -> port 8188 -> Templates -> LTX-2.5 Image-to-Video.'
echo 'Choose the INT8 ConvRot transformer and encoder, and the video VAE requested by your workflow.'
echo 'Both standard and Conv video VAEs are installed, along with the audio VAE.'
echo 'Select a first-frame image; the template requires one.'
echo 'Prompt Enhance uses the Comfy-Org Gemma e2b file; disable it if you prefer verbatim prompts.'
echo 'For a first test: 768x432, 81 frames, 24 fps; use the distilled template sampling defaults.'
echo "Install log: $LOG"
