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
GRAPHQL = "https://api.runpod.io/graphql"


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
            # RunPod's Cloudflare front end rejects this API client when the
            # User-Agent resembles an automated browser signature.
            "User-Agent": "curl/8.0",
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


def apply_graphql_template(template_id: str | None, payload: dict, labels: dict, key: str) -> dict:
    """Apply fields REST v1 omits from the UI, notably named port mappings."""
    ports = payload.get("ports", [])
    port_configs = {}
    for port in ports:
        number = port.split("/", 1)[0]
        port_configs.setdefault(number, {"port": number, "name": labels.get(port, number)})
    gql_input = {
        "name": payload["name"],
        "imageName": payload["imageName"],
        "containerDiskInGb": payload["containerDiskInGb"],
        "volumeInGb": payload.get("volumeInGb", 0),
        "volumeMountPath": payload.get("volumeMountPath", ""),
        "isPublic": payload["isPublic"],
        "isServerless": payload["isServerless"],
        "dockerArgs": "",
        "ports": ",".join(ports),
        "portsConfig": list(port_configs.values()),
        "env": [
            {"key": name, "value": str(value)}
            for name, value in payload.get("env", {}).items()
        ],
        "readme": payload.get("readme", ""),
        "category": payload.get("category", "NVIDIA"),
    }
    if template_id:
        gql_input["id"] = template_id
    query = "mutation($input: SaveTemplateInput!) { saveTemplate(input:$input) { id name imageName isPublic portsConfig { port name } } }"
    req = urllib.request.Request(
        GRAPHQL,
        data=json.dumps({"query": query, "variables": {"input": gql_input}}).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
    )
    with urllib.request.urlopen(req, timeout=45) as response:
        result = json.load(response)
    if result.get("errors"):
        message = result["errors"][0].get("message", "GraphQL template update failed")
        raise RuntimeError(message)
    return result["data"]["saveTemplate"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", help="Override the immutable image reference in the JSON payload")
    parser.add_argument("--drop-port", action="append", default=[], help="Remove a port entry (repeatable), for example 8080/http")
    parser.add_argument("--update-existing", action="store_true", help="PATCH the existing same-name template instead of refusing a duplicate")
    parser.add_argument("--dry-run", action="store_true", help="Print payload without calling RunPod")
    args = parser.parse_args()

    payload = json.loads((ROOT / "config/runpod-template.json").read_text(encoding="utf-8"))
    labels = payload.pop("portLabels", {})
    if args.image:
        payload["imageName"] = args.image
    payload["ports"] = [port for port in payload.get("ports", []) if port not in args.drop_port]
    labels = {port: label for port, label in labels.items() if port not in args.drop_port}
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
        if not args.update_existing:
            info = ", ".join(f"id={item.get('id')} image={item.get('imageName')}" for item in matches)
            raise SystemExit(f"A template named {payload['name']!r} already exists ({info}). No duplicate was created.")
        result = apply_graphql_template(matches[0]["id"], payload, labels, key)
        print(f"Updated RunPod template {result.get('name')} (id {result.get('id')}) using {result.get('imageName')}.")
        return

    result = apply_graphql_template(None, payload, labels, key)
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
