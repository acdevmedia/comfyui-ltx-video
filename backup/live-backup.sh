#!/usr/bin/env bash
set -Eeuo pipefail
APP=/opt/ltx25-studio/backup/s3_backup.py
STATE=/workspace/.ltx25-studio/backup
mkdir -p "$STATE"
exec 9>"$STATE/watcher.lock"
if ! flock -n 9; then echo '[backup] A watcher already holds the persistent lock.'; exit 0; fi
exec python "$APP" watch
