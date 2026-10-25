#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
REGISTRY=ghcr.io
IMAGE=ghcr.io/acdevmedia/ltx-studio
VERSION="${VERSION:-}"
if [[ -z "$VERSION" ]]; then echo 'Set VERSION to a dated or semantic release tag.' >&2; exit 2; fi
if [[ -n "$(git status --porcelain --untracked-files=all)" ]]; then
  echo 'Commit the release source tree before publishing so the version tag identifies the built source.' >&2
  exit 4
fi

TOKEN="${GITHUB_PACKAGES_PAT:-}"
if [[ -z "$TOKEN" && -f "${GHCR_ENV_FILE:-.env}" ]]; then
  TOKEN="$(python3 - "${GHCR_ENV_FILE:-.env}" <<'PY'
import sys
for line in open(sys.argv[1],encoding='utf-8'):
    line=line.strip()
    if line.startswith('GITHUB_PACKAGES_PAT='):
        value=line.split('=',1)[1].strip()
        if len(value)>=2 and value[0]==value[-1] and value[0] in "\"'": value=value[1:-1]
        print(value); break
PY
)"
fi
if [[ -z "$TOKEN" ]]; then echo 'Set GITHUB_PACKAGES_PAT in the environment or ignored .env.' >&2; exit 3; fi

USERNAME="${GHCR_USERNAME:-}"
if [[ -z "$USERNAME" ]]; then
  PROFILE="$(printf 'header = "Authorization: Bearer %s"\n' "$TOKEN" | curl --config - -fsS https://api.github.com/user)"
  USERNAME="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["login"])' <<<"$PROFILE")"
fi
printf '%s' "$TOKEN" | docker login "$REGISTRY" --username "$USERNAME" --password-stdin >/dev/null
unset TOKEN PROFILE
TAGS=(-t "$IMAGE:$VERSION")
if [[ "${PUBLISH_LATEST:-false}" =~ ^(1|true|yes)$ ]]; then TAGS+=(-t "$IMAGE:latest"); fi
docker buildx build --platform linux/amd64 --push "${TAGS[@]}" .
echo "Published tag: $IMAGE:$VERSION"
docker buildx imagetools inspect "$IMAGE:$VERSION" | sed -n '1,18p'
echo 'Set the GHCR package visibility to Public in GitHub package settings if anonymous RunPod pulls are intended.'
