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
"$APP/docker/initialise-workspace.sh"
python "$APP/scripts/validate-hf-secret.py"
if command -v nvidia-smi >/dev/null 2>&1; then nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || echo "[startup] WARNING: GPU query failed"; else echo "[startup] ERROR: NVIDIA runtime is unavailable; select a CUDA GPU pod."; exit 41; fi
python -c 'import torch; print("[startup] PyTorch",torch.__version__,"CUDA",torch.version.cuda,"available",torch.cuda.is_available()); assert torch.cuda.is_available()' || { echo "[startup] ERROR: PyTorch cannot access CUDA. Verify the RunPod GPU/runtime."; exit 42; }
if [[ "${AUTO_DOWNLOAD_MODELS:-true}" =~ ^(1|true|yes)$ ]]; then python "$APP/scripts/download-models.py"; else python "$APP/scripts/verify-models.py" --required; fi
python "$APP/scripts/verify-workflows.py" --installed
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
echo "[startup] Models and packaged workflows verified. Starting ComfyUI on :${COMFYUI_PORT:-8188}."
nginx -t
nginx -g 'daemon off;' >>/workspace/logs/nginx.log 2>&1 & children+=("$!")
"$APP/docker/start-comfyui.sh" >>/workspace/logs/comfyui.log 2>&1 & children+=("$!")
while true; do
  for pid in "${children[@]}"; do
    if ! kill -0 "$pid" 2>/dev/null; then wait "$pid" || rc=$?; echo "[startup] Managed service exited (status ${rc:-0}); see /workspace/logs."; exit "${rc:-1}"; fi
  done
  sleep 2
done
