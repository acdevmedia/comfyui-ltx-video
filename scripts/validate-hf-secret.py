#!/usr/bin/env python3
"""Fail with setup guidance when the RunPod Hugging Face secret is absent."""
import os
import sys


def resolved(value: str | None) -> bool:
    candidate = (value or "").strip()
    return bool(candidate) and not candidate.startswith(("{{ RUNPOD_SECRET_", "YOUR_", "OPTIONAL_"))


def main() -> int:
    if os.environ.get("AUTO_DOWNLOAD_MODELS", "true").strip().lower() not in {"1", "true", "yes"}:
        print("[setup] Automatic model downloads are disabled; Hugging Face secret check skipped.", flush=True)
        return 0
    if not any(resolved(os.environ.get(name)) for name in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN")):
        print("[setup] ERROR: Hugging Face secret is empty or unresolved. In RunPod, create a Secret named HUGGINGFACE_TOKEN. The template maps it to HF_TOKEN with {{ RUNPOD_SECRET_HUGGINGFACE_TOKEN }}. Accept the gated LTX-2.5 model terms for that account, then restart the Pod. The token value is never logged.", file=sys.stderr, flush=True)
        return 20
    print("[setup] Hugging Face secret is present; validating model access during provisioning.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
