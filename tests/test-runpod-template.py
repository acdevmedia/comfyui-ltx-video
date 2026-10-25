import json
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
template = json.loads((root / "config/runpod-template.json").read_text())
assert template["name"] == "LTX 2.5 Distilled Video and one click"
assert template["category"] == "NVIDIA" and template["isPublic"] is True
assert template["isServerless"] is False
assert template["containerDiskInGb"] == 100
assert "volumeMountPath" not in template and "volumeInGb" not in template
assert {"8188/http", "8888/http", "8675/http", "22/tcp", "8080/tcp", "22/udp", "8080/udp"}.issubset(template["ports"])
assert template["env"]["HF_TOKEN"] == "YOUR_HUGGING_FACE_TOKEN"
assert list(template["env"]) == sorted(template["env"])
assert "S3_SECRET_ACCESS_KEY" in template["env"]
assert not any(key.startswith("AWS_") for key in template["env"])
result = subprocess.run(
    [sys.executable, str(root / "scripts/create-runpod-template.py"), "--dry-run"],
    check=True,
    capture_output=True,
    text=True,
)
assert json.loads(result.stdout)["imageName"] == template["imageName"]
assert template["dockerEntrypoint"] == [] and template["dockerStartCmd"] == []
print("RunPod template payload is public, container-only, port-configured, and contains no populated secrets.")
