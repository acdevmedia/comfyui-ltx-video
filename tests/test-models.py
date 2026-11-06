import json
import importlib.util
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
assert all('group' in m for m in manifest['models']), 'every model must have an explicit download group'
for m in manifest['models']:
    if 'revision' in m:
        # Hugging Face hides a gated file's hash without an accepted licence; scripts/pin-gated-models.py fetches it.
        assert len(m['revision'])==40 and m['size']>0 and len(m.get('sha256') or '')==64, m['id']
loader=importlib.util.spec_from_file_location('download_models',root/'scripts/download-models.py')
downloader=importlib.util.module_from_spec(loader); loader.loader.exec_module(downloader)
default_ids={m['id'] for m in downloader.selected_models(manifest,'default',True)}
optional_ids={m['id'] for m in downloader.selected_models(manifest,'optional',True)}
ingredient_ids={m['id'] for m in downloader.selected_models(manifest,'ingredients',True)}
adapter_ids={m['id'] for m in downloader.selected_models(manifest,'adapters',True)}
assert 'gemma4-enhancer-bf16' in optional_ids and 'gemma4-enhancer-bf16' not in default_ids
assert {'ltx25-transformer-int8','ltx25-text-encoder-int8','gemma4-enhancer-int8'} <= default_ids
assert {'ingredients-transformer-bf16','ingredients-text-encoder-bf16','ingredients-ic-lora'} <= default_ids
assert ingredient_ids == {'ingredients-transformer-bf16','ingredients-text-encoder-bf16','ingredients-ic-lora'}
# A licence-gated LoRA must never stop startup, so nothing in this group is fetched unless asked for.
assert {'crossview-ic-lora','relight-ic-lora','day-to-night-ic-lora'}|ingredient_ids == adapter_ids
assert not {'crossview-ic-lora','relight-ic-lora','day-to-night-ic-lora'} & default_ids
assert 'transition-lora' in default_ids and 'transition-lora' in {m['id'] for m in downloader.selected_models(manifest,'default',False)}
assert all((root/'scripts'/name).is_file() for name in ('download-ingredients-models.sh','download-adapter-models.sh','download-optional-models.sh','download-all-models.sh'))
print(f"Model manifest is structurally valid ({len(ids)} declared files).")
with tempfile.TemporaryDirectory() as temp:
    env=os.environ.copy(); env['COMFYUI_DIR']=temp; env['MODEL_MANIFEST']=str(root/'versions/ltx-2.5/config/models.json')
    env.pop('HF_TOKEN',None); env.pop('HUGGING_FACE_HUB_TOKEN',None)
    result=subprocess.run([sys.executable,str(root/'scripts/download-models.py')],env=env,text=True,capture_output=True)
    assert result.returncode==20, result.stdout+result.stderr
    assert 'Hugging Face authentication is missing or unresolved' in result.stderr
    assert 'token=' not in result.stdout+result.stderr
print('Missing-token provisioning diagnostic is distinct and does not expose a token.')
