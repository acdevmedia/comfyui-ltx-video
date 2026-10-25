import importlib.util
from pathlib import Path

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("proxy_guard", root / "scripts/patch-comfyui-proxy-guard.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

fixture = "async def sample_middleware(request):\n" + module.ORIGINAL
patched, changed = module.patch_text(fixture)
assert changed is True
compile(patched, "ComfyUI/server.py", "exec")
assert "request.path == '/'" in patched
assert "request.method == 'GET'" in patched
assert "Sec-Fetch-Mode') == 'navigate'" in patched
assert "Sec-Fetch-Dest') == 'document'" in patched
assert "if not safe_runpod_navigation" in patched
again, changed = module.patch_text(patched)
assert again == patched and changed is False
try:
    module.patch_text("unexpected source")
except ValueError:
    pass
else:
    raise AssertionError("Unexpected ComfyUI source must fail closed")
print("RunPod proxy navigation patch allows only root document GETs and fails closed.")
