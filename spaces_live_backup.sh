#!/usr/bin/env bash
# Continuous, non-deleting MP4 backup from RunPod ComfyUI to DigitalOcean Spaces.
set -Eeuo pipefail

SOURCE_DIR="${SOURCE_DIR:-/workspace/ComfyUI/output/video}"
CONFIG_FILE="${CONFIG_FILE:-$HOME/.config/ltx-spaces.env}"
STATE_DIR="${STATE_DIR:-/workspace/.spaces-live-backup}"
LOG_FILE="$STATE_DIR/backup.log"
LOCK_FILE="$STATE_DIR/backup.lock"
RECHECK_SECONDS="${RECHECK_SECONDS:-120}"
SETTLE_SECONDS="${SETTLE_SECONDS:-8}"
mkdir -p "$STATE_DIR"

if [[ "${1:-}" == "--install" ]]; then
  if ! command -v aws >/dev/null || ! command -v inotifywait >/dev/null || ! command -v flock >/dev/null; then
    if [[ "$(id -u)" == 0 ]]; then
      apt-get update && apt-get install -y awscli inotify-tools util-linux
    else
      echo "Install awscli, inotify-tools and util-linux as root first." >&2; exit 1
    fi
  fi
  nohup "$0" --run >>"$LOG_FILE" 2>&1 </dev/null &
  echo "Launched backup watcher (PID $!). Log: $LOG_FILE"
  exit 0
fi
if [[ "${1:-}" != "--run" ]]; then
  echo "Usage: $0 --install | --run"; exit 2
fi

exec 9>"$LOCK_FILE"
if ! flock -n 9; then echo "Backup watcher already running."; exit 0; fi

if [[ -f "$CONFIG_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$CONFIG_FILE"
  set +a
fi
: "${SPACES_BUCKET:?Set SPACES_BUCKET in config or environment}"
: "${SPACES_REGION:?Set SPACES_REGION in config or environment}"
: "${AWS_ACCESS_KEY_ID:?Set AWS_ACCESS_KEY_ID in config or environment}"
: "${AWS_SECRET_ACCESS_KEY:?Set AWS_SECRET_ACCESS_KEY in config or environment}"
for cmd in aws inotifywait flock; do command -v "$cmd" >/dev/null || { echo "Missing $cmd" >&2; exit 1; }; done

# Stable instance-specific path avoids collisions with other RunPod containers.
# /workspace must persist between container restarts for the ID to remain stable.
ID_FILE="$STATE_DIR/instance-id"
if [[ ! -s "$ID_FILE" ]]; then
  (umask 077; printf '%s-%s\n' "$(date -u +%Y%m%dT%H%M%SZ)" "$(od -An -N5 -tx1 /dev/urandom | tr -d ' \n')" > "$ID_FILE")
fi
INSTANCE_ID="$(cat "$ID_FILE")"
BASE_PREFIX="${SPACES_PREFIX:-comfyui-backups}"
BASE_PREFIX="${BASE_PREFIX#/}"; BASE_PREFIX="${BASE_PREFIX%/}"
DEST="s3://${SPACES_BUCKET}/${BASE_PREFIX}/${INSTANCE_ID}/video"
ENDPOINT="https://${SPACES_REGION}.digitaloceanspaces.com"
export AWS_DEFAULT_REGION="$SPACES_REGION" AWS_EC2_METADATA_DISABLED=true

backup() {
  if [[ ! -d "$SOURCE_DIR" ]]; then
    echo "$(date -Is) Source absent, will retry: $SOURCE_DIR"
    return 0
  fi
  echo "$(date -Is) Checking $SOURCE_DIR -> $DEST"
  # Copy new/changed MP4 files. Never propagate local deletions to Spaces.
  if aws --endpoint-url "$ENDPOINT" s3 sync "$SOURCE_DIR" "$DEST" \
      --exclude '*' --include '*.mp4' --include '*.MP4' \
      --no-progress --only-show-errors; then
    echo "$(date -Is) Backup pass complete"
  else
    echo "$(date -Is) ERROR: backup failed; will retry" >&2
  fi
}

echo "$(date -Is) Live backup started (instance $INSTANCE_ID)"
backup
while true; do
  if [[ -d "$SOURCE_DIR" ]]; then
    # Timeout ensures periodic reconciliation, even if no changes arrive.
    # close_write/moved_to avoid acting on most partially written files.
    inotifywait -q -r -e close_write,moved_to,create,delete \
      --timeout "$RECHECK_SECONDS" "$SOURCE_DIR" >/dev/null 2>&1 || true
    sleep "$SETTLE_SECONDS"
  else
    sleep "$RECHECK_SECONDS"
  fi
  backup
done
