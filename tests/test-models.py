import json
import os, subprocess, sys, tempfile
from pathlib import Path

root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'versions/ltx-2.5/config/models.json').read_text())
ids=[m['id'] for m in manifest['models']]
assert len(ids)==len(set(ids)), 'duplicate model id'
targets=[m.get('target',m['file']) for m in manifest['models']]
assert len(targets)==len(set(targets)), 'duplicate model target'
for m in manifest['models']:
    assert '/' in m.get('target',m['file']), f"model path must be category-relative: {m['id']}"
assert any(m['id']=='ingredients-ic-lora' and m['repo']=='Lightricks/LTX-2.5-22b-IC-LoRA-Ingredients' for m in manifest['models'])
assert all(m.get('default') for m in manifest['models']), 'default provision manifest should be explicit'
print(f"Model manifest is structurally valid ({len(ids)} declared files).")
with tempfile.TemporaryDirectory() as temp:
    env=os.environ.copy(); env['COMFYUI_DIR']=temp; env['MODEL_MANIFEST']=str(root/'versions/ltx-2.5/config/models.json')
    env.pop('HF_TOKEN',None); env.pop('HUGGING_FACE_HUB_TOKEN',None)
    result=subprocess.run([sys.executable,str(root/'scripts/download-models.py')],env=env,text=True,capture_output=True)
    assert result.returncode==20, result.stdout+result.stderr
    assert 'Hugging Face authentication is missing or unresolved' in result.stderr
    assert 'token=' not in result.stdout+result.stderr
print('Missing-token provisioning diagnostic is distinct and does not expose a token.')
