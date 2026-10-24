#!/usr/bin/env python3
"""Create the public RunPod Pod template from config/runpod-template.json."""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = "https://rest.runpod.io/v1"


def local_env() -> dict[str, str]:
    values = {}
    path = ROOT / ".env"
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
    return values


def request(method: str, url: str, key: str, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "acdev-ltx-studio-template",
        },
    )
    with urllib.request.urlopen(req, timeout=45) as response:
        body = response.read()
        return response.status, (json.loads(body) if body else None)


def check_public_image(image: str) -> None:
    name, tag = image.rsplit(":", 1)
    repo = name.removeprefix("ghcr.io/")
    url = f"https://ghcr.io/v2/{repo}/manifests/{tag}"
    accept = "application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json"
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"Accept": accept})
        try:
            response = urllib.request.urlopen(req, timeout=30)
        except urllib.error.HTTPError as exc:
            challenge = exc.headers.get("WWW-Authenticate", "")
            match = re.search(r'realm="([^"]+)"', challenge)
            if exc.code != 401 or not match:
                raise
            token_url = f"{match.group(1)}?service=ghcr.io&scope=repository:{repo}:pull"
            with urllib.request.urlopen(token_url, timeout=30) as token_response:
                token_data = json.load(token_response)
                bearer = token_data.get("token") or token_data.get("access_token")
            authorized = urllib.request.Request(url, method="HEAD", headers={"Accept": accept, "Authorization": f"Bearer {bearer}"})
            response = urllib.request.urlopen(authorized, timeout=30)
        with response:
            if response.status != 200:
                raise RuntimeError(f"GHCR returned HTTP {response.status} for {image}.")
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise RuntimeError(f"{image} is not anonymously pullable yet. Set the GHCR package visibility to Public before creating a public RunPod template.") from None
        if exc.code == 404:
            raise RuntimeError(f"Image tag is not published in GHCR: {image}") from None
        raise RuntimeError(f"Could not verify {image} in GHCR (HTTP {exc.code}).") from None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", help="Override the immutable image reference in the JSON payload")
    parser.add_argument("--dry-run", action="store_true", help="Print payload without calling RunPod")
    args = parser.parse_args()

    payload = json.loads((ROOT / "config/runpod-template.json").read_text(encoding="utf-8"))
    if args.image:
        payload["imageName"] = args.image
    if args.dry_run:
        print(json.dumps(payload, indent=2))
        return

    key = os.environ.get("RUNPOD_API_KEY") or local_env().get("RUNPOD_API_KEY")
    if not key:
        raise SystemExit("RUNPOD_API_KEY is missing; set it in the shell environment or ignored LTX-SETUP/.env.")
    check_public_image(payload["imageName"])
    _, existing = request("GET", f"{API}/templates", key)
    if not isinstance(existing, list):
        raise SystemExit("RunPod returned an unexpected template list; refusing to create a duplicate.")
    matches = [item for item in existing if item.get("name") == payload["name"]]
    if matches:
        info = ", ".join(f"id={item.get('id')} image={item.get('imageName')}" for item in matches)
        raise SystemExit(f"A template named {payload['name']!r} already exists ({info}). No duplicate was created.")

    status, result = request("POST", f"{API}/templates", key, payload)
    if status not in (200, 201):
        raise SystemExit(f"RunPod template creation returned HTTP {status}.")
    print(f"Created RunPod template {result.get('name')} (id {result.get('id')}) using {result.get('imageName')}.")
    print("Template is public. Add HF_TOKEN and any S3 credentials through RunPod Secrets before starting a Pod.")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as exc:
        detail = exc.read(1000).decode("utf-8", "replace")
        print(f"RunPod API returned HTTP {exc.code}: {detail}", file=sys.stderr)
        raise SystemExit(1)
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"Network request failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
