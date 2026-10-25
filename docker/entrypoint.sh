#!/usr/bin/env bash
set -Eeuo pipefail
APP=/opt/ltx25-studio
mkdir -p /workspace/logs
exec > >(tee -a /workspace/logs/startup.log) 2>&1
children=()
background=()
shutdown() {
  trap - TERM INT EXIT
  for pid in "${children[@]:-}" "${background[@]:-}"; do kill -TERM "$pid" 2>/dev/null || true; done
  wait || true
}
trap shutdown TERM INT EXIT
echo "[startup] ACDEV LTX-2.5 Studio starting ($(date -Is))"
echo "[startup] This first-start setup checks the GPU, verifies Hugging Face access, downloads missing models, installs workflows, and then starts ComfyUI. Model downloads can take several minutes."
echo "[startup] Detailed logs: /workspace/logs/startup.log (ComfyUI: comfyui.log; downloads are also printed below)."
echo "[startup] Container disk is temporary. Download important outputs or enable S3 backup before deleting/replacing this Pod."
echo "[startup] Hugging Face and S3 secret values are never printed."
"$APP/docker/initialise-workspace.sh"
echo "[startup] Checking ComfyUI's RunPod proxy compatibility before launch."
python "$APP/scripts/patch-comfyui-proxy-guard.py" "$APP/ComfyUI/server.py"
echo "[setup 1/6] Checking Hugging Face credentials and model access."
python "$APP/scripts/validate-hf-secret.py"
echo "[setup 2/6] Checking that an NVIDIA GPU and compatible CUDA-enabled PyTorch are available."
if command -v nvidia-smi >/dev/null 2>&1; then nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || echo "[startup] WARNING: GPU query failed; CUDA validation below will provide the detailed error."; else echo "[startup] ERROR: NVIDIA runtime is unavailable. Select a RunPod NVIDIA CUDA GPU (A100 80 GB recommended), then start a new Pod."; exit 41; fi
python -c 'import torch; print("[startup] Technical details: PyTorch",torch.__version__,"CUDA",torch.version.cuda,"CUDA available",torch.cuda.is_available()); assert torch.cuda.is_available()' || { echo "[startup] ERROR: PyTorch cannot access CUDA. The container started, but video generation cannot run without the assigned NVIDIA GPU/runtime. Verify the Pod GPU selection and RunPod NVIDIA container runtime."; exit 42; }
echo "[setup 3/6] Checking required LTX-2.5 files and downloading anything missing. This default model set is about 108 GiB; Hugging Face terms must be accepted for every gated repository."
if [[ "${AUTO_DOWNLOAD_MODELS:-true}" =~ ^(1|true|yes)$ ]]; then python "$APP/scripts/download-models.py"; else echo "[models] Automatic downloads are disabled; verifying that all required weights are already installed."; python "$APP/scripts/verify-models.py" --required; fi
echo "[setup 4/6] Verifying all seven packaged filmmaker workflows and their node graphs."
python "$APP/scripts/verify-workflows.py" --installed
echo "[setup 5/6] Starting output thumbnail generation and checking optional cloud backup."
python "$APP/frontend/video-gallery/thumbnailer.py" >>/workspace/logs/thumbnailer.log 2>&1 & background+=("$!")
if [[ "${REALTIME_BACKUP:-false}" =~ ^(1|true|yes)$ ]]; then
  missing_backup=()
  for key in S3_BUCKET S3_ACCESS_KEY_ID S3_SECRET_ACCESS_KEY; do
    value="${!key:-}"
    if [[ -z "$value" || "$value" == YOUR_* || "$value" == *"{{ RUNPOD_SECRET_"* ]]; then missing_backup+=("$key"); fi
  done
  if ((${#missing_backup[@]})); then
    echo "[backup] ERROR: REALTIME_BACKUP=true, but required S3 settings are empty or unresolved: ${missing_backup[*]}. Add RunPod Secrets named S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY, set S3_BUCKET to the destination bucket, and confirm the template secret references resolve. Backup was not started; ComfyUI will continue. No credential values were logged."
  else
    echo "[backup] S3 configuration present; starting non-deleting output backup."
    "$APP/backup/live-backup.sh" >>/workspace/logs/backup.log 2>&1 & background+=("$!")
  fi
else echo "[backup] Disabled (REALTIME_BACKUP is not true)."; fi
if [[ "${ENABLE_JUPYTER:-false}" =~ ^(1|true|yes)$ ]]; then
  if [[ -z "${JUPYTER_TOKEN:-}" || "${JUPYTER_TOKEN:-}" == *"{{ RUNPOD_SECRET_"* ]]; then echo "[startup] ERROR: Jupyter is enabled but its secret is empty or unresolved. Create a RunPod Secret named JUPYTER_TOKEN, verify the template reference, and restart the Pod. No token value was logged."; exit 43; fi
  python -m jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --allow-root --ServerApp.token="$JUPYTER_TOKEN" >>/workspace/logs/jupyter.log 2>&1 & children+=("$!")
fi
if [[ -n "${PUBLIC_KEY:-}" ]]; then install -d -m 700 /root/.ssh; printf '%s\n' "$PUBLIC_KEY" >> /root/.ssh/authorized_keys; chmod 600 /root/.ssh/authorized_keys; ssh-keygen -A; /usr/sbin/sshd; fi
echo "[setup 6/6] Starting ComfyUI and web access services."
echo "[startup] ComfyUI listens on 0.0.0.0:${COMFYUI_PORT:-8188}; use the Pod Connect tab's HTTP 8188 link."
nginx -t
nginx -g 'daemon off;' >>/workspace/logs/nginx.log 2>&1 & children+=("$!")
"$APP/docker/start-comfyui.sh" >>/workspace/logs/comfyui.log 2>&1 & children+=("$!")
comfy_pid="${children[-1]}"
echo "[startup] Waiting for ComfyUI's local readiness endpoint (up to 4 minutes)."
ready=0
for _ in $(seq 1 120); do
  if curl -fsS --max-time 3 "http://127.0.0.1:${COMFYUI_PORT:-8188}/system_stats" >/dev/null 2>&1; then ready=1; break; fi
  if ! kill -0 "$comfy_pid" 2>/dev/null; then
    echo "[startup] ERROR: ComfyUI exited before becoming ready. Last 80 lines from /workspace/logs/comfyui.log follow:"
    tail -n 80 /workspace/logs/comfyui.log || true
    exit 44
  fi
  sleep 2
done
if [[ "$ready" != 1 ]]; then
  echo "[startup] ERROR: ComfyUI did not answer /system_stats within 4 minutes. Last 80 lines from /workspace/logs/comfyui.log follow:"
  tail -n 80 /workspace/logs/comfyui.log || true
  echo "[startup] Check missing-node or CUDA errors above. The complete log is /workspace/logs/comfyui.log."
  exit 45
fi
echo "[ready] ComfyUI is responding on port ${COMFYUI_PORT:-8188}; RunPod Connect should now mark HTTP 8188 Ready."
echo "[ready] Open ComfyUI from the Pod Connect tab. If using the old image, paste the proxy URL into a fresh blank browser tab to avoid ComfyUI's old cross-site navigation guard."
echo "[ready] Technical check passed: GET /system_stats returned HTTP 200. Logs: /workspace/logs/startup.log and /workspace/logs/comfyui.log."
while true; do
  for pid in "${children[@]}"; do
    if ! kill -0 "$pid" 2>/dev/null; then wait "$pid" || rc=$?; echo "[startup] Managed service exited (status ${rc:-0}); see /workspace/logs."; exit "${rc:-1}"; fi
  done
  sleep 2
done
