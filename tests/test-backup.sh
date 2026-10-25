#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
set +e
output="$(env -u S3_BUCKET -u S3_ACCESS_KEY_ID -u S3_SECRET_ACCESS_KEY -u S3_ENDPOINT_URL python3 "$ROOT/backup/s3_backup.py" verify 2>&1)"
status=$?
set -e
[[ $status -ne 0 ]]
[[ "$output" == *"missing/invalid configuration"* ]]
[[ "$output" != *"S3_SECRET_ACCESS_KEY="* ]]
echo 'Backup configuration diagnostics reject a missing bucket without exposing credentials.'
