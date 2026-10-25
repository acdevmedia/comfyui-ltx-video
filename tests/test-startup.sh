#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
for f in "$ROOT"/docker/*.sh "$ROOT"/backup/*.sh "$ROOT"/scripts/*.sh; do bash -n "$f"; done
python3 -m py_compile "$ROOT/scripts/download-models.py" "$ROOT/scripts/validate-hf-secret.py" "$ROOT/scripts/verify-models.py" "$ROOT/scripts/verify-workflows.py" "$ROOT/scripts/package-workflows.py" "$ROOT/scripts/install-workflows.py" "$ROOT/backup/s3_backup.py" "$ROOT/scripts/benchmark.py"
echo 'Shell syntax and Python compilation checks passed.'
