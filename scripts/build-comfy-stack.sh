#!/usr/bin/env bash
set -Eeuo pipefail

APP=/opt/ltx25-studio
PROFILE="$APP/versions/${LTX_VERSION}/profile.json"
if [[ ! -f "$PROFILE" ]]; then
  echo "No packaged LTX profile found for LTX_VERSION=${LTX_VERSION:-unset}." >&2
  exit 2
fi

mapfile -t SETTINGS < <(python3 - "$PROFILE" <<'PY'
import json, sys
runtime = json.load(open(sys.argv[1], encoding="utf-8"))["runtime"]
for key in (
    "cuda_version", "torch_version", "torchvision_version", "torchaudio_version",
    "torch_index_url", "comfyui_commit", "manager_commit", "custom_scripts_commit",
    "ltxvideo_commit", "huggingface_hub_version", "transformers_version", "diffusers_version",
    "comfy_aimdo_version", "comfy_kitchen_version", "av_version", "boto3_version",
    "watchdog_version", "jupyterlab_version", "sageattention_version",
):
    print(runtime[key])
PY
)

if [[ "${SETTINGS[0]}" != "$CUDA_VERSION" ]]; then
  echo "CUDA_VERSION=${CUDA_VERSION} does not match profile ${LTX_VERSION} (${SETTINGS[0]})." >&2
  exit 3
fi

pip install --no-cache-dir --upgrade pip
pip install --no-cache-dir \
  "torch==${SETTINGS[1]}" "torchvision==${SETTINGS[2]}" "torchaudio==${SETTINGS[3]}" \
  --index-url "${SETTINGS[4]}"

git clone https://github.com/comfyanonymous/ComfyUI.git "$APP/ComfyUI"
cd "$APP/ComfyUI"
git checkout --detach "${SETTINGS[5]}"
python3 - <<'PY'
import re
from pathlib import Path
path = Path("requirements.txt")
lines = path.read_text().splitlines()
path.write_text("\n".join(line for line in lines if not re.match(r"^\s*(torch|torchvision|torchaudio)(?:[<>=!~;#\[]|$)", line, re.I)) + "\n")
PY
pip install --no-cache-dir -r requirements.txt

mkdir -p custom_nodes
git clone https://github.com/ltdrdata/ComfyUI-Manager.git custom_nodes/ComfyUI-Manager
git -C custom_nodes/ComfyUI-Manager checkout --detach "${SETTINGS[6]}"

git clone https://github.com/pythongosssss/ComfyUI-Custom-Scripts.git custom_nodes/ComfyUI-Custom-Scripts
git -C custom_nodes/ComfyUI-Custom-Scripts checkout --detach "${SETTINGS[7]}"
if [[ -f custom_nodes/ComfyUI-Custom-Scripts/requirements.txt ]]; then
  pip install --no-cache-dir -r custom_nodes/ComfyUI-Custom-Scripts/requirements.txt
fi

git clone https://github.com/Lightricks/ComfyUI-LTXVideo.git custom_nodes/ComfyUI-LTXVideo
git -C custom_nodes/ComfyUI-LTXVideo checkout --detach "${SETTINGS[8]}"
pip install --no-cache-dir -r custom_nodes/ComfyUI-LTXVideo/requirements.txt

PINS=(
  "huggingface_hub==${SETTINGS[9]}" "transformers==${SETTINGS[10]}"
  "diffusers==${SETTINGS[11]}" "comfy-aimdo==${SETTINGS[12]}"
  "comfy-kitchen==${SETTINGS[13]}" "av==${SETTINGS[14]}"
  "boto3==${SETTINGS[15]}" "watchdog==${SETTINGS[16]}"
  "jupyterlab==${SETTINGS[17]}"
  "sageattention==${SETTINGS[18]}"
)
pip install --no-cache-dir "${PINS[@]}"
pip check
