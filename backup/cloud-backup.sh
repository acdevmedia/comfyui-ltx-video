#!/usr/bin/env bash
set -Eeuo pipefail
exec python /opt/ltx25-studio/backup/s3_backup.py once
