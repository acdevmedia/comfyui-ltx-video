#!/usr/bin/env python3
"""Provision only declared LTX files; resumable through Hugging Face Hub cache."""
import json
import argparse
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(os.environ.get("COMFYUI_DIR", "/workspace/ComfyUI"))
MODEL_ROOT = ROOT / "models"
MANIFEST = Path(os.environ.get("MODEL_MANIFEST", "/opt/ltx25-studio/versions/ltx-2.5/config/models.json"))
HF_HOME = Path(os.environ.get("HF_HOME", "/workspace/.cache/huggingface"))


def fail(message: str, code: int = 1) -> None:
    print(f"[models] ERROR: {message}", file=sys.stderr, flush=True)
    raise SystemExit(code)


def usable_token(value: str | None) -> bool:
    token = (value or "").strip()
    return bool(token) and not token.startswith("{{ RUNPOD_SECRET_") and not token.startswith("YOUR_")


def valid_local_file(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return False
    try:
        from safetensors import safe_open
        with safe_open(str(path), framework="pt", device="cpu") as handle:
            return bool(handle.keys())
    except Exception:
        return False


def selected_models(data: dict, group: str, adapter_downloads: bool) -> list[dict]:
    models = data["models"]
    if group == "all":
        return models
    if group == "optional":
        return [m for m in models if m.get("optional") or m.get("group") == "optional"]
    if group == "ingredients":
        return [m for m in models if m.get("group") == "ingredients"]
    selected = [m for m in models if m.get("default", False) and not m.get("optional", False)]
    if not adapter_downloads:
        selected = [m for m in selected if m.get("group") != "ingredients"]
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", choices=("default", "ingredients", "optional", "all"), default="default", help="Model set to download (default follows the RunPod startup profile).")
    args = parser.parse_args()
    if args.group == "default" and os.environ.get("AUTO_DOWNLOAD_MODELS", "true").lower() not in {"1", "true", "yes"}:
        print("[models] Automatic downloads disabled by AUTO_DOWNLOAD_MODELS.", flush=True)
        return

    data = json.loads(MANIFEST.read_text())
    adapter_downloads = os.environ.get("AUTO_DOWNLOAD_ADAPTERS", "true").lower() in {"1", "true", "yes"}
    models = selected_models(data, args.group, adapter_downloads)
    if not models:
        fail(f"The '{args.group}' model group is empty in {MANIFEST}.")
    print(f"[models] Provisioning group '{args.group}' ({len(models)} files).", flush=True)
    pending = [m for m in models if not valid_local_file(MODEL_ROOT / m.get("target", m["file"]))]
    if not pending:
        print(f"[models] All {len(models)} default model files are present.", flush=True)
        return

    candidates = [os.environ.get("HF_TOKEN"), os.environ.get("HUGGING_FACE_HUB_TOKEN")]
    token = next((value.strip() for value in candidates if usable_token(value)), None)
    if not token:
        fail("Hugging Face authentication is missing or unresolved. In RunPod, create a Secret named HUGGINGFACE_TOKEN and make sure the template maps it to HF_TOKEN ({{ RUNPOD_SECRET_HUGGINGFACE_TOKEN }}). Accept the gated LTX-2.5 model terms for that account, then restart the Pod. No token value was logged.", 20)

    os.environ["HF_HOME"] = str(HF_HOME)
    try:
        from huggingface_hub import HfApi, hf_hub_download
        from huggingface_hub.errors import GatedRepoError, HfHubHTTPError, RepositoryNotFoundError
    except ImportError:
        fail("huggingface_hub is missing from the image.")

    api = HfApi(token=token)
    file_info = {}
    expected_total = 0
    for item in pending:
        repo, filename = item["repo"], item["file"]
        print(f"[models] Checking {repo}:{filename}", flush=True)
        try:
            info = api.get_paths_info(repo, paths=[filename], repo_type="model")[0]
        except GatedRepoError:
            fail(f"Access to {repo} is gated. Accept its model terms while signed in to the Hugging Face account used by this token.", 21)
        except RepositoryNotFoundError:
            fail(f"Repository or file is unavailable: {repo}:{filename}. Verify model access and the pinned manifest.", 22)
        except HfHubHTTPError as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in (401, 403):
                fail(f"Hugging Face rejected access to {repo}. Check token validity, read permissions, and gated-model acceptance.", 23)
            fail(f"Hugging Face metadata request failed for {repo} (HTTP {status or 'unknown'}). Check network access and retry.", 24)
        except Exception as exc:
            fail(f"Could not query Hugging Face for {repo} ({type(exc).__name__}). Check network access and retry.", 24)
        expected = getattr(info, "size", None)
        file_info[item["id"]] = (info, expected)
        if expected: expected_total += expected

    free = shutil.disk_usage(MODEL_ROOT).free
    if expected_total and free < expected_total + (2 * 1024**3):
        fail(f"Insufficient free storage before download: remaining model files need about {expected_total / 1024**3:.1f} GiB plus 2 GiB headroom; have {free / 1024**3:.1f} GiB.", 25)
    if expected_total:
        print(f"[models] Storage preflight passed: {expected_total / 1024**3:.1f} GiB required; {free / 1024**3:.1f} GiB free.", flush=True)

    for item in pending:
        repo, filename = item["repo"], item["file"]
        target_rel = item.get("target", filename)
        target = MODEL_ROOT / target_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        _, expected = file_info[item["id"]]
        if expected:
            free = shutil.disk_usage(MODEL_ROOT).free
            if free < expected + (2 * 1024**3):
                fail(f"Insufficient free storage for {target_rel}: need about {expected / 1024**3:.1f} GiB plus 2 GiB headroom; have {free / 1024**3:.1f} GiB.", 25)
        try:
            local_dir = MODEL_ROOT if target_rel == filename else target.parent
            downloaded = Path(hf_hub_download(repo_id=repo, filename=filename, repo_type="model", local_dir=str(local_dir), token=token))
            if downloaded.resolve() != target.resolve():
                shutil.copy2(downloaded, target)
            if not valid_local_file(target):
                fail(f"Download finished without a valid file at {target_rel}.", 26)
            if expected and target.stat().st_size != expected:
                fail(f"Downloaded size does not match Hugging Face metadata for {target_rel}; it will be retried next startup.", 27)
            print(f"[models] Ready: {target_rel} ({target.stat().st_size / 1024**3:.2f} GiB)", flush=True)
        except SystemExit:
            raise
        except Exception as exc:
            fail(f"Download failed for {repo}:{filename} ({type(exc).__name__}). Check network and token permissions; retry is safe.", 28)

    print(f"[models] All files in group '{args.group}' are ready.", flush=True)


if __name__ == "__main__":
    main()
