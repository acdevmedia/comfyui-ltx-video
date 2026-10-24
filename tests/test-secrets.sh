#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
git check-ignore -q .env
grep -qx '\.env' .dockerignore
! git ls-files --error-unmatch .env >/dev/null 2>&1
echo 'Local .env is ignored by Git and Docker build context.'
