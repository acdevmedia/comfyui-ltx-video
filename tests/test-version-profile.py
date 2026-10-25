import json
import os
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
version = os.environ.get("LTX_VERSION", "ltx-2.5")
profile_dir = root / "versions" / version
profile = json.loads((profile_dir / "profile.json").read_text())
assert profile["id"] == version
assert len(profile["assets"]["workflow_files"]) == 10
assert profile["default_workflow"] in profile["assets"]["workflow_files"]
for rel in (profile["assets"]["models"], profile["assets"]["adapters"]):
    assert (profile_dir / rel).is_file(), rel
for name in profile["assets"]["workflow_files"]:
    graph = profile_dir / profile["assets"]["workflows"] / name
    assert json.loads(graph.read_text()).get("nodes"), name
manifest = json.loads((profile_dir / profile["assets"]["models"]).read_text())
for item in manifest["models"]:
    assert item.get("repo") and item.get("file") and item.get("id")
result = subprocess.run(
    [sys.executable, str(root / "scripts/profile-build-args.py"), "--version", version],
    check=True,
    capture_output=True,
    text=True,
)
assert f"ltx_version={version}" in result.stdout
assert f"cuda_version={profile['runtime']['cuda_version']}" in result.stdout
print(f"Version profile {version} and its packaged assets are consistent.")
