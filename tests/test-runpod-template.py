import json
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
template = json.loads((root / "config/runpod-template.json").read_text())
assert template["name"] == "ACDEV LTX-2.5 Studio"
assert template["category"] == "NVIDIA" and template["isPublic"] is True
assert template["isServerless"] is False
assert template["volumeMountPath"] == "/workspace" and template["volumeInGb"] >= 200
assert {"8188/http", "8080/http", "8888/http", "22/tcp"}.issubset(template["ports"])
assert template["env"]["HF_TOKEN"] == "YOUR_HUGGING_FACE_TOKEN"
assert template["env"]["AWS_SECRET_ACCESS_KEY"] == ""
result = subprocess.run(
    [sys.executable, str(root / "scripts/create-runpod-template.py"), "--dry-run"],
    check=True,
    capture_output=True,
    text=True,
)
assert json.loads(result.stdout)["imageName"] == template["imageName"]
print("RunPod template payload is public, persistent, port-configured, and contains no secrets.")
