#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
set +e
output="$(env -u S3_BUCKET -u SPACES_BUCKET -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY -u S3_ENDPOINT_URL -u SPACES_REGION python3 "$ROOT/backup/s3_backup.py" verify 2>&1)"
status=$?
set -e
[[ $status -ne 0 ]]
[[ "$output" == *"missing/invalid configuration"* ]]
[[ "$output" != *"AWS_SECRET_ACCESS_KEY="* ]]
echo 'Backup configuration diagnostics reject a missing bucket without exposing credentials.'
