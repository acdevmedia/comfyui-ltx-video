#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
git check-ignore -q .env
grep -qx '\.env' .dockerignore
! git ls-files --error-unmatch .env >/dev/null 2>&1
echo 'Local .env is ignored by Git and Docker build context.'

set +e
output="$(env -u HF_TOKEN -u HUGGING_FACE_HUB_TOKEN AUTO_DOWNLOAD_MODELS=true python3 "$ROOT/scripts/validate-hf-secret.py" 2>&1)"
status=$?
set -e
[[ $status -eq 20 ]]
[[ "$output" == *"Secret named HUGGINGFACE_TOKEN"* ]]
[[ "$output" != *"HF_TOKEN="* ]]
secret_value='hf_secret_must_not_be_logged'
output="$(env HF_TOKEN="$secret_value" AUTO_DOWNLOAD_MODELS=true python3 "$ROOT/scripts/validate-hf-secret.py" 2>&1)"
[[ "$output" == *"secret is present"* ]]
[[ "$output" != *"$secret_value"* ]]
echo 'Startup rejects a missing Hugging Face RunPod Secret with safe setup guidance.'
