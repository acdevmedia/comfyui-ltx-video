#!/usr/bin/env python3
"""Read the immutable runtime build inputs for one LTX model profile."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--version", default="ltx-2.5")
parser.add_argument("--github-output", help="Append GitHub Actions outputs to this file")
args = parser.parse_args()
profile_path = ROOT / "versions" / args.version / "profile.json"
profile = json.loads(profile_path.read_text())
if profile.get("id") != args.version:
    raise SystemExit(f"Profile id does not match directory: {profile_path}")
runtime = profile["runtime"]
values = {"ltx_version": args.version, "cuda_version": runtime["cuda_version"]}
lines = [f"{key}={value}" for key, value in values.items()]
if args.github_output:
    with open(args.github_output, "a", encoding="utf-8") as stream:
        stream.write("\n".join(lines) + "\n")
else:
    print("\n".join(lines))
