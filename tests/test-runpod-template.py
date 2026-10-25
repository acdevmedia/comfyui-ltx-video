import json
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
template = json.loads((root / "config/runpod-template.json").read_text())
assert template["name"] == "LTX 2.5 Distilled ComfyUI Video One-Click"
assert template["category"] == "NVIDIA" and template["isPublic"] is True
assert template["isServerless"] is False
assert template["containerDiskInGb"] == 200
assert "volumeMountPath" not in template and "volumeInGb" not in template
assert {"8188/http", "8888/http", "8675/http", "22/tcp", "8080/tcp", "22/udp", "8080/udp"}.issubset(template["ports"])
assert template["env"]["HF_TOKEN"] == "{{ RUNPOD_SECRET_HUGGINGFACE_TOKEN }}"
assert template["env"]["TINI_SUBREAPER"] == "1"
assert template["env"]["S3_ACCESS_KEY_ID"] == "{{ RUNPOD_SECRET_S3_ACCESS_KEY_ID }}"
assert template["env"]["S3_SECRET_ACCESS_KEY"] == "{{ RUNPOD_SECRET_S3_SECRET_ACCESS_KEY }}"
assert list(template["env"]) == sorted(template["env"])
assert "S3_SECRET_ACCESS_KEY" in template["env"]
assert not any(key.startswith("AWS_") for key in template["env"])
assert not any(key.startswith("DOWNLOAD_") for key in template["env"])
assert not any(any(marker in key or marker in value for marker in ("SPACES_", "AWS_")) for key, value in template["env"].items())
result = subprocess.run(
    [sys.executable, str(root / "scripts/create-runpod-template.py"), "--dry-run"],
    check=True,
    capture_output=True,
    text=True,
)
assert json.loads(result.stdout)["imageName"] == template["imageName"]
assert template["dockerEntrypoint"] == [] and template["dockerStartCmd"] == []
print("RunPod template payload is public, container-only, port-configured, and uses RunPod secret references.")
