import json, subprocess, sys
from pathlib import Path
import os, shutil, tempfile

root=Path(__file__).resolve().parents[1]
version=root/'versions'/'ltx-2.5'
subprocess.run([sys.executable,str(root/'scripts/verify-workflows.py')],check=True)
for name in sorted(p.name for p in (version/'workflows').glob('0*.json')):
    d=json.loads((version/'workflows'/name).read_text())
    assert d.get('nodes') and d.get('links') is not None, name
    assert any(n.get('title')=='About the Negative Prompt' for n in d['nodes']), f'{name}: missing negative prompt note'
    if name.startswith('02_'):
        assert not any(n.get('type')=='LoadImage' for n in d['nodes']), 'T2V must not have an image input node'
    if name.startswith('07_'):
        blob=json.dumps(d)
        assert 'LTXAddVideoICLoRAGuide' in blob or 'Ingredients' in blob
        assert 'ltx-2.5-22b-ic-lora-ingredients-0.9.safetensors' in blob
    if name in ('04_LTX25_Audio_to_Video.json','05_LTX25_Text_to_Audio.json'):
        blob=json.dumps(d)
        assert 'gemma4_e2b_it_int8_convrot.safetensors' in blob, f'{name}: must use the default-downloaded prompt enhancer'
        assert 'gemma4_e2b_it_bf16.safetensors' not in blob, f'{name}: must not require the optional BF16 prompt enhancer'
        assert 'ltx-2.5-22b-distilled-transformer-bf16.safetensors' not in blob, f'{name}: must share the default INT8 transformer'
        assert 'gemma4-12b-with-proj-ltx-2.5-bf16.safetensors' not in blob, f'{name}: must share the default INT8 text encoder'
    if name[:3] in ('01_','02_','03_','04_','06_'):
        assert '"ltx-2.5-video-vae-bf16.safetensors"' not in json.dumps(d), f'{name}: must default to the convolutional video decoder'
    if name[:3] in ('02_','03_'):
        # The promoted negative prompt must feed the subgraph's negative CLIPTextEncode, not just sit on the panel.
        control=next(n for n in d['nodes'] if any(i.get('name')=='director_negative_prompt' for i in n.get('inputs',[])))
        sub=next(s for s in d['definitions']['subgraphs'] if s['id']==control['type'])
        slot=[i['name'] for i in sub['inputs']].index('director_negative_prompt')
        link=next(l for l in sub['links'] if l['origin_id']==-10 and l['origin_slot']==slot)
        encoder=next(n for n in sub['nodes'] if n['id']==link['target_id'])
        assert encoder['type']=='CLIPTextEncode' and encoder['inputs'][link['target_slot']]['name']=='text', f'{name}: negative prompt is not wired to an encoder'
        assert d['last_link_id']>=max(l['id'] for l in sub['links']), f'{name}: root link counter is behind subgraph link ids'
    if name == '05_LTX25_Text_to_Audio.json':
        # Keep the Load Models outputs connected to the matching exposed
        # Input Parameters slots: ckpt_path=7, text_encoder=8, enhancer=9.
        root_links={link[0]:link[4] for link in d['links']}
        assert root_links.get(13812)==7, 'T2A checkpoint path must target ckpt_path'
        assert root_links.get(13811)==8, 'T2A text encoder must target text_encoder'
        assert root_links.get(4)==9, 'T2A prompt enhancer must target text_enhancer'
print('Workflow JSON and mode-specific assertions passed.')
with tempfile.TemporaryDirectory() as temp:
    temp=Path(temp); app=temp/'app'; (app/'workflows').mkdir(parents=True)
    (app/'versions'/'ltx-2.5').mkdir(parents=True)
    shutil.copy2(version/'profile.json',app/'versions'/'ltx-2.5'/'profile.json')
    shutil.copytree(version/'workflows',app/'versions'/'ltx-2.5'/'workflows')
    env=os.environ.copy(); env['LTX_APP_DIR']=str(app); env['LTX_VERSION']='ltx-2.5'; env['COMFYUI_DIR']=str(temp/'comfy')
    env['LTX_DEFAULT_WORKFLOW']='02_LTX25_Text_to_Video'; env['LTX_DEFAULT_DURATION']='12'
    subprocess.run([sys.executable,str(root/'scripts/install-workflows.py')],env=env,check=True,capture_output=True,text=True)
    installed=Path(env['COMFYUI_DIR'])/'user/default/workflows'
    assert len(list(installed.glob('0*.json')))==7
    default=json.loads((app/'ComfyUI/web/templates/default.json').read_text())
    assert default['extra']['acdev_studio']['workflow']=='Text to Video — Filmmaker'
    graph=json.loads((installed/'02_LTX25_Text_to_Video.json').read_text())
    assert next(n for n in graph['nodes'] if n['id']==405)['widgets_values'][2]==12
    custom=installed/'user-made.json'; custom.write_text('{"user":true}')
    before=custom.read_text()
    subprocess.run([sys.executable,str(root/'scripts/install-workflows.py')],env=env,check=True,capture_output=True,text=True)
    assert custom.read_text()==before
print('First-boot workflow selection/defaults and persistent file preservation passed.')
