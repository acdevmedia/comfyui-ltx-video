import json, subprocess, sys
from pathlib import Path
import os, shutil, tempfile

root=Path(__file__).resolve().parents[1]
version=root/'versions'/'ltx-2.5'
sys.path.insert(0,str(root/'scripts'))
from workflow_panels import flatten
schemas=json.loads((version/'config/node-schemas.json').read_text())
model_files={Path(m['file']).name for m in json.loads((version/'config/models.json').read_text())['models']}
IC_LORAS={'11_':'LTX2.3-22B_IC-LoRA-CrossView-Prompt_v0.9_13700.safetensors','12_':'ltx-2.3-22b-ic-lora-relight-1.0.safetensors','13_':'ltx-2.5-22b-ic-lora-day-to-night-0.9.safetensors'}

def check_ic_lora(name,d):
    """Nothing runs here, so prove the graph is wired correctly from its schemas and links."""
    flat=flatten(d)
    def one(typ):
        found=[(p,n) for p,n in flat.items() if n[0]==typ]
        assert len(found)==1,(name,typ,len(found))
        return found[0]
    for path,(typ,_,inputs) in flat.items():
        spec=schemas[typ]['input']
        for field,value in inputs.items():
            if value[0]!='node':continue
            source=schemas[flat[value[1]][0]]
            assert value[2]<len(source['output']),(name,typ,field,'no such output')
            got=source['output'][value[2]]
            want=next((s[0] for group in spec.values() for f,s in group.items() if f==field),None)
            # Autogrow sockets such as values.a accept either number type, and an INT may feed a FLOAT.
            assert want is None or isinstance(want,list) or got in want.split(',') or (got,want)==('INT','FLOAT'),(name,typ,field,got,want)
    def source_type(path,field):
        return flat[flat[path][2][field][1]][0]
    ic,_=one('LTXICLoRALoaderModelOnly');guide,_=one('LTXAddVideoICLoRAGuide');guider,_=one('CFGGuider');crop,_=one('LTXVCropGuides');decode,_=one('VAEDecodeTiled');video,_=one('CreateVideo');concat,_=one('LTXVConcatAVLatent')
    assert source_type(ic,'model')=='UNETLoader' and source_type(guider,'model')=='LTXICLoRALoaderModelOnly'
    assert source_type(guider,'positive')=='LTXAddVideoICLoRAGuide' and source_type(crop,'positive')=='LTXAddVideoICLoRAGuide'
    assert source_type(decode,'samples')=='LTXVCropGuides'
    relighting=name.startswith('12_')
    # Relight follows Lightricks' workflow, which lets the audio latent run free; the others hold the clip's sound.
    if relighting:assert source_type(concat,'audio_latent')=='LTXVEmptyLatentAudio' and not any(n[0]=='LTXVSetAudioRefTokens' for n in flat.values())
    else:assert flat[concat][2]['audio_latent'][1]==one('LTXVSetAudioRefTokens')[0]
    # Same take: the clip's own waveform is muxed back, and the guide is the clip (with the ball, for Relight, last).
    assert source_type(video,'audio')=='TrimAudioDuration'
    painted=source_type(guide,'image')
    assert painted==('ImageCompositeMasked' if relighting else 'ImageScale'),name
    if relighting:
        # The default ball follows Lightricks' example and must agree with the default words.
        sphere=one('SphereLightManualNode')[1][1]
        assert sphere[:3]==[90.0,15.0,2.0],sphere
        sized=flat[flat[one('ImageCompositeMasked')[0]][2]['source'][1]]
        assert sized[1][0]=='area',sized[1]
        assert 'low-angle sunlight from the right' in json.dumps(d)
subprocess.run([sys.executable,str(root/'scripts/verify-workflows.py')],check=True)
profile_names=json.loads((version/'profile.json').read_text())['assets']['workflow_files']
for name in profile_names:
    d=json.loads((version/'workflows'/name).read_text())
    assert d.get('nodes') and d.get('links') is not None, name
    assert not any(n['type'] in ('Note','MarkdownNote') for n in d['nodes']), f'{name}: notes should be hidden'
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
    every_node=d['nodes']+[n for sub in d.get('definitions',{}).get('subgraphs',[]) for n in sub.get('nodes',[])]
    types={n['type'] for n in every_node}
    if name[:3] in ('04_','05_','07_','08_','09_','10_','11_','12_','13_'):
        # One-panel layout: only the inputs, the controls panel and the save node sit on the canvas.
        visible=[n.get('title') or n['type'] for n in d['nodes'] if n['type']!='MarkdownNote']
        assert len(visible)<=4, f'{name}: canvas should stay a single controls panel, found {visible}'
    if name[:3] in ('08_','09_','10_','11_','12_','13_'):
        # Video in, video out: each graph loads a clip and saves an MP4, and keeps the clip's sound path.
        assert {'LoadVideo','GetVideoComponents','CreateVideo','SaveVideo','AudioMerge'} <= types, f'{name}: missing video-in/video-out nodes'
    if name[:3] in ('08_','09_'):
        assert {'LTXVAddGuide','BatchImagesNode','AudioConcat','LTXVSetAudioRefTokens','LTXVCropGuides'} <= types, f'{name}: extension must stitch picture and sound'
        assert ('ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors' in json.dumps(d)), f'{name}: extension uses the default INT8 stack'
    if name=='10_LTX25_New_Angle.json':
        blob=json.dumps(d)
        assert 'LTXAddVideoICLoRAGuide' in blob and 'ltx-2.5-22b-ic-lora-ingredients-0.9.safetensors' in blob
        assert 'LoadImage' in types, 'New Angle needs an uploaded reference sheet'
        assert 'LTXVSetAudioRefTokens' in blob and 'VAEEncodeAudio' in blob, 'New Angle must lock the source sound'
    if name[:3] in IC_LORAS:
        blob=json.dumps(d)
        assert IC_LORAS[name[:3]] in blob, f'{name}: wrong IC-LoRA'
        assert 'ltx-2.5-22b-distilled-transformer-bf16.safetensors' in blob, f'{name}: IC-LoRAs use the BF16 stack'
        assert 'comfy-int8-convrot' not in blob, f'{name}: must not mix in the INT8 stack'
        assert set(s for s in __import__('re').findall(r'[\w.\-]+\.safetensors',blob))<=model_files, f'{name}: uses a file the manifest does not fetch'
        canvas={n['type'] for n in d['nodes']}
        assert 'LoadVideo' in canvas and 'LoadImage' not in types, f'{name}: the clip is the only guide'
        assert ('SphereLightManualNode' in canvas)==name.startswith('12_'), f'{name}: the browser only renders the ball for a node on the canvas'
        check_ic_lora(name,d)
    if name.startswith('03_'):
        # The Transition LoRA sits between the model and the guider, off by default, driven from the panel.
        control=next(n for n in d['nodes'] if any(i.get('name')=='transition_strength' for i in n.get('inputs',[])))
        sub=next(s for s in d['definitions']['subgraphs'] if s['id']==control['type'])
        lora=next(n for n in sub['nodes'] if n['type']=='LoraLoaderModelOnly')
        assert lora['widgets_values']==['ltx2.3-transition.safetensors',0.0]
        slot=[i['name'] for i in sub['inputs']].index('transition_strength')
        link=next(l for l in sub['links'] if l['origin_id']==-10 and l['origin_slot']==slot)
        assert link['target_id']==lora['id'] and lora['inputs'][link['target_slot']]['name']=='strength_model'
        into=next(l for l in sub['links'] if l['target_id']==lora['id'] and l['target_slot']==0)
        out=next(l for l in sub['links'] if l['origin_id']==lora['id'])
        assert next(n for n in sub['nodes'] if n['id']==into['origin_id'])['type']=='UNETLoader'
        assert next(n for n in sub['nodes'] if n['id']==out['target_id'])['type']=='LTXVDualCFGGuider'
        assert [i.get('label') for i in control['inputs'] if i.get('widget')][-2:]==['Transition LoRA strength','Exact Frame']
        assert control['widgets_values'][-2:]==[0.0,False]
        assert lora['inputs'][0]['link']==into['id'] and next(n for n in sub['nodes'] if n['id']==out['target_id'])['inputs'][out['target_slot']]['link']==out['id']
    if name == '05_LTX25_Text_to_Audio.json':
        # Keep the Load Models outputs connected to the matching exposed
        # Input Parameters slots: ckpt_path=7, text_encoder=8, enhancer=9.
        # The panel keeps these link ids, so look in every graph, not just the canvas.
        all_links=d['links']+[l for sub in d.get('definitions',{}).get('subgraphs',[]) for l in sub.get('links',[])]
        root_links={(l['id'] if isinstance(l,dict) else l[0]):(l['target_slot'] if isinstance(l,dict) else l[4]) for l in all_links}
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
    assert sorted(p.name for p in installed.glob('*.json') if p.name!='user-made.json')==sorted(profile_names)
    default=json.loads((app/'ComfyUI/web/templates/default.json').read_text())
    assert default['extra']['acdev_studio']['workflow']=='Text to Video — Filmmaker'
    graph=json.loads((installed/'02_LTX25_Text_to_Video.json').read_text())
    assert next(n for n in graph['nodes'] if n['id']==405)['widgets_values'][2]==12
    for audio in ('04_LTX25_Audio_to_Video.json','05_LTX25_Text_to_Audio.json'):
        panel=next(n for n in json.loads((installed/audio).read_text())['nodes'] if any(i.get('label')=='Clip Length (seconds)' for i in n.get('inputs',[])))
        fields=[i['label'] for i in panel['inputs'] if i.get('widget')]
        assert panel['widgets_values'][fields.index('Clip Length (seconds)')]==12, f'{audio}: default duration not applied to the panel'
    custom=installed/'user-made.json'; custom.write_text('{"user":true}')
    before=custom.read_text()
    subprocess.run([sys.executable,str(root/'scripts/install-workflows.py')],env=env,check=True,capture_output=True,text=True)
    assert custom.read_text()==before
print('First-boot workflow selection/defaults and persistent file preservation passed.')
