#!/usr/bin/env bash
# Back up ComfyUI MP4 files to a unique, private DigitalOcean Spaces prefix.
set -Eeuo pipefail

SOURCE_DIR="${SOURCE_DIR:-/workspace/ComfyUI/output/video}"
CONFIG_FILE="${CONFIG_FILE:-$HOME/.config/ltx-spaces.env}"

if [[ -f "$CONFIG_FILE" ]]; then
  # Configuration file is trusted local shell syntax; keep it chmod 600.
  set -a
  # shellcheck disable=SC1090
  source "$CONFIG_FILE"
  set +a
fi

: "${S3_BUCKET:?Set S3_BUCKET in the config or environment}"
: "${S3_REGION:?Set S3_REGION (e.g. sfo3)}"
: "${S3_ACCESS_KEY_ID:?Set S3_ACCESS_KEY_ID}"
: "${S3_SECRET_ACCESS_KEY:?Set S3_SECRET_ACCESS_KEY}"

command -v aws >/dev/null 2>&1 || { echo 'AWS CLI missing. Install: apt-get update && apt-get install -y awscli' >&2; exit 1; }
[[ -d "$SOURCE_DIR" ]] || { echo "Missing source folder: $SOURCE_DIR" >&2; exit 1; }

# One unique prefix per invocation; S3 prefixes are virtual folders.
STAMP="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
SUFFIX="$(od -An -N4 -tx1 /dev/urandom | tr -d ' \n')"
BASE_PREFIX="${S3_PREFIX:-ltx25-studio}"
BASE_PREFIX="${BASE_PREFIX#/}"; BASE_PREFIX="${BASE_PREFIX%/}"
DEST="s3://${S3_BUCKET}/${BASE_PREFIX}/${STAMP}-${SUFFIX}"
ENDPOINT="${S3_ENDPOINT_URL:-https://${S3_REGION}.digitaloceanspaces.com}"

export AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY_ID" AWS_SECRET_ACCESS_KEY="$S3_SECRET_ACCESS_KEY"
export AWS_DEFAULT_REGION="${S3_REGION}"
[[ -n "${S3_SESSION_TOKEN:-}" && "$S3_SESSION_TOKEN" != OPTIONAL_* ]] && export AWS_SESSION_TOKEN="$S3_SESSION_TOKEN"
export AWS_EC2_METADATA_DISABLED=true

count=0
failed=0
while IFS= read -r -d '' file; do
  relative="${file#"$SOURCE_DIR"/}"
  printf 'Uploading: %s\n' "$relative"
  if aws --endpoint-url "$ENDPOINT" s3 cp "$file" "$DEST/$relative" \
    --only-show-errors --no-progress --content-type 'video/mp4'; then
    ((count+=1))
  else
    ((failed+=1))
    printf 'FAILED: %s\n' "$relative" >&2
  fi
done < <(find "$SOURCE_DIR" -type f -iname '*.mp4' -print0 | sort -z)

printf '\nDestination: %s/\nUploaded: %d, failed: %d\n' "$DEST" "$count" "$failed"
if (( count == 0 )); then echo 'No MP4s uploaded.' >&2; exit 1; fi
if (( failed > 0 )); then exit 1; fi
printf 'Backup completed. Local files were not changed.\n'
