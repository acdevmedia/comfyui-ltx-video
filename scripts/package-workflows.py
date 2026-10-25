#!/usr/bin/env python3
"""Build filmmaker-named workflow assets from the preserved master and official graph refs."""
import copy, json, uuid
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
VERSION=__import__('os').environ.get('LTX_VERSION','ltx-2.5')
PROFILE_DIR=ROOT/'versions'/VERSION
WORK=PROFILE_DIR/'workflows'
PROFILE=json.loads((PROFILE_DIR/'profile.json').read_text())
PRODUCT=PROFILE['product_name']
REF=ROOT/'archive/official-workflow-references'
# Video-in workflows: UI graphs converted by ComfyUI's own frontend from scripts/v2v_graphs.py.
V2V=ROOT/'archive/v2v-workflow-sources'

def read(path): return json.loads(path.read_text())
def set_duration(data, value=30):
    for node in data.get('nodes',[]):
        title=(node.get('title') or '').lower()
        if 'duration' in title and node.get('widgets_values') and isinstance(node['widgets_values'][0],(int,float)):
            node['widgets_values'][0]=value
        for sub in node.get('widgets_values_named',{}):
            pass
    for sub in data.get('definitions',{}).get('subgraphs',[]):
        for node in sub.get('nodes',[]):
            title=(node.get('title') or '').lower()
            if 'duration' in title and node.get('widgets_values') and isinstance(node['widgets_values'][0],(int,float)):
                node['widgets_values'][0]=value

def rename(data, title):
    data.setdefault('extra',{})['acdev_studio']={'product':PRODUCT,'version':VERSION,'workflow':title}
    data['extra'].setdefault('ds',{})

def use_default_prompt_enhancer(data):
    """Use the INT8 Gemma enhancer that startup already provisions by default."""
    old='gemma4_e2b_it_bf16.safetensors'
    new='gemma4_e2b_it_int8_convrot.safetensors'
    def replace(value):
        if isinstance(value,dict):
            for key,item in value.items(): value[key]=replace(item)
        elif isinstance(value,list):
            for index,item in enumerate(value): value[index]=replace(item)
        elif isinstance(value,str):
            value=value.replace(old,new)
            value=value.replace('Google Gemma 4 E2B IT]', 'Google Gemma 4 E2B IT INT8 ConvRot (included in the default download)]')
        return value
    replace(data)

def use_int8_stack(data):
    """Share the INT8 transformer/encoder with the video graphs so switching modes avoids a BF16 reload."""
    swaps={
        'ltx-2.5-22b-distilled-transformer-bf16.safetensors':'ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors',
        'gemma4-12b-with-proj-ltx-2.5-bf16.safetensors':'gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors',
    }
    def replace(value):
        if isinstance(value,dict):
            for key,item in value.items(): value[key]=replace(item)
        elif isinstance(value,list):
            for index,item in enumerate(value): value[index]=replace(item)
        elif isinstance(value,str):
            for old,new in swaps.items(): value=value.replace(old,new)
        return value
    replace(data)

def use_conv_video_vae(data):
    """Select the faster convolutional video decoder; notes that describe both decoders are left as written."""
    old='ltx-2.5-video-vae-bf16.safetensors'
    new='ltx-2.5-video-vae-conv-bf16.safetensors'
    def replace(value):
        if isinstance(value,dict):
            if value.get('name')==old and isinstance(value.get('url'),str):
                value['name']=new; value['url']=value['url'].replace(old,new)
            for key,item in value.items(): value[key]=replace(item)
        elif isinstance(value,list):
            for index,item in enumerate(value): value[index]=replace(item)
        elif value==old:
            value=new
        return value
    replace(data)

NEGATIVE_LABEL='Negative Prompt (CFG 1.0: little/no effect)'
NEGATIVE_PROMPT='blurry, out of focus, oversharpened, waxy skin, deformed faces, incorrect hands, extra fingers, duplicate limbs, identity drift, changing clothing, flicker, frame jitter, camera jump, unwanted cuts, camera zoom, sudden push-in, exposure pumping, inconsistent lighting, color shifts, CGI appearance, distorted voices, robotic speech, broken lip sync, added narration, unwanted subtitles, watermarks, audio pops, audio clipping'

def expose_negative_prompt(data, control_id, encoder_id):
    """Promote the subgraph's negative CLIPTextEncode text to the filmmaker control panel, as 01/06 already do.

    LTXVDualCFGGuider at video/audio CFG 1.0 skips the negative pass, so this only matters when CFG is raised.
    """
    control=next(n for n in data['nodes'] if n['id']==control_id)
    sub=next(s for s in data['definitions']['subgraphs'] if s['id']==control['type'])
    encoder=next(n for n in sub['nodes'] if n['id']==encoder_id)
    link_id=max([sub['state']['lastLinkId'],data.get('last_link_id',0)]+[l['id'] for l in sub['links']])+1
    sub['inputs'].append({'id':str(uuid.uuid5(uuid.NAMESPACE_URL,f"{sub['id']}/director_negative_prompt")),'name':'director_negative_prompt',
        'type':'STRING','linkIds':[link_id],'label':NEGATIVE_LABEL,'pos':list(sub['inputs'][-1].get('pos',[0,0]))})
    sub['links'].append({'id':link_id,'origin_id':-10,'origin_slot':len(sub['inputs'])-1,'target_id':encoder_id,'target_slot':len(encoder['inputs']),'type':'STRING'})
    encoder['inputs'].append({'localized_name':'text','name':'text','type':'STRING','widget':{'name':'text'},'link':link_id})
    encoder['widgets_values'][0]=NEGATIVE_PROMPT
    sub['state']['lastLinkId']=link_id
    # Link ids share one counter across the root graph and its subgraphs.
    data['last_link_id']=max(data.get('last_link_id',0),link_id)
    control['inputs'].append({'label':NEGATIVE_LABEL,'name':'director_negative_prompt','type':'STRING','widget':{'name':'director_negative_prompt'},'link':None})
    control['widgets_values'].append(NEGATIVE_PROMPT)

NEGATIVE_NOTE='''## About the negative prompt

The negative prompt is a list of things you would rather not see or hear, such as flicker, extra fingers or background music.

**With this workflow's default settings it has no effect.** LTX-2.5 Distilled runs at a guidance (CFG) of 1.0, and at that setting ComfyUI skips the negative prompt entirely to save time.

It only comes into play if you raise a CFG value above 1.0 in the sampler settings. Sampling then takes roughly twice as long, and the distilled model is not tuned for higher guidance, so try it on a short clip first.

For most shots, steer the result from the main prompt instead. Describe what you want ("steady locked-off camera", "soft window light", "no music") rather than listing what you don't.'''

EXTEND_NOTE='''## How to extend a clip ({direction})

1. Upload your clip in **Your Clip**.
2. Write **{prompt_title}**. Describe the action and any dialogue, and keep the people, wardrobe, location and lens the same as your clip.
3. Set **Seconds to Add** (5 is a good start).
4. **Frames of Your Clip to Match** sets how much of your clip's {edge} the model sees. 25 frames is about one second at 24 fps. More frames give smoother motion across the join; the value is rounded to 9, 17, 25, 33 and so on.
5. Run. The saved video is {result}, with sound.

Your clip is resized and centre-cropped to **Width x Height** (default 1280 x 704). Use multiples of 32 that match your clip's shape. The new section's sound is generated, using five seconds of your clip's own sound as a voice reference so the voices stay the same. Extend the result again to build a longer scene.'''

NEW_ANGLE_NOTE='''## How to shoot a new angle

This re-stages a moment of your clip from a different camera position while keeping your clip's **exact sound**, so it cuts straight into your edit on the same audio track.

1. Upload your clip in **Your Clip**. Set **Start Time** and **Shot Length**. Five seconds is what the model was trained on.
2. Upload a **Reference Sheet**: one image with a clean panel for each person (a face close-up and a full-body view), each important prop, and the location, on a plain black background with no text. Make it from stills of your clip with an image tool. Bigger panels carry over better.
3. In **Describe the Sheet and the New Angle**, keep the two parts. "Reference sheet:" names each panel by its position. "Generated video:" describes the new camera position and what happens.
4. Run. The result carries your clip's original sound, so line it up at the same timecode in your editor.

**Do not use a frame grabbed straight from your clip as the sheet.** The model copies its framing instead of moving the camera. This is a re-staged shot rather than a true camera move: the people, set and light stay close to the sheet, but the performance is newly generated. It needs the Ingredients models (start the Pod with AUTO_DOWNLOAD_ADAPTERS=true, or run scripts/download-ingredients-models.sh).'''

def add_note(data, title, text):
    """Place a note to the left of everything already in the graph."""
    nodes=data['nodes']
    state=data.get('state') or {}
    node_id=max([n['id'] for n in nodes]+[data.get('last_node_id') or 0,state.get('lastNodeId',0)])+1
    nodes.append({'id':node_id,'type':'MarkdownNote','pos':[min(n['pos'][0] for n in nodes)-560,min(n['pos'][1] for n in nodes)],'size':[500,520],
        'flags':{},'order':len(nodes),'mode':0,'inputs':[],'outputs':[],'title':title,'properties':{},
        'widgets_values':[text],'color':'#222','bgcolor':'#000'})
    if 'last_node_id' in data: data['last_node_id']=node_id
    if 'lastNodeId' in state: state['lastNodeId']=node_id

def add_negative_prompt_note(data):
    """Explain in plain English, next to the controls, why the negative prompt is inert at CFG 1.0."""
    nodes=data['nodes']
    anchor=max(nodes,key=lambda n:len(n['widgets_values']) if isinstance(n.get('widgets_values'),list) else 0)
    state=data.get('state') or {}
    node_id=max([n['id'] for n in nodes]+[data.get('last_node_id') or 0,state.get('lastNodeId',0)])+1
    nodes.append({'id':node_id,'type':'MarkdownNote','pos':[min(n['pos'][0] for n in nodes)-560,anchor['pos'][1]],'size':[500,420],
        'flags':{},'order':len(nodes),'mode':0,'inputs':[],'outputs':[],'title':'About the Negative Prompt','properties':{},
        'widgets_values':[NEGATIVE_NOTE],'color':'#222','bgcolor':'#000'})
    if 'last_node_id' in data: data['last_node_id']=node_id
    if 'lastNodeId' in state: state['lastNodeId']=node_id

def write(name, data):
    add_negative_prompt_note(data)
    (WORK/name).write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')

def main():
    master=read(WORK/'LTX25_Filmmaker_Workflow_v9_Advanced.json')
    i2v=copy.deepcopy(master); rename(i2v,'Image to Video — Filmmaker'); set_duration(i2v)
    # Existing resolution selector: aspect ratio, megapixels, divisibility.
    for n in i2v['nodes']:
        if n.get('type')=='LoadImage': n['widgets_values']=['','image']; n['title']='Opening Image'
        if n.get('type')=='ResolutionSelector' and len(n.get('widgets_values',[]))>1: n['widgets_values'][1]=0.5
        if n.get('id')==398:
            n['title']='Image to Video — Filmmaker Controls'
            n['widgets_values'][2]=30
            if 'value_2' in n.get('widgets_values_named',{}): n['widgets_values_named']['value_2']=30
    use_conv_video_vae(i2v); write('01_LTX25_Image_to_Video.json',i2v)

    t2v=read(REF/'video_ltx2_5_t2v.json'); rename(t2v,'Text to Video — Filmmaker')
    for n in t2v['nodes']:
        if n.get('type')=='SaveVideo': n['widgets_values'][0]='video/LTX25_Text_to_Video'
        if n.get('id')==405:
            n['title']='Text to Video — Filmmaker Controls'
            n['widgets_values'][1]=False
            n['widgets_values'][2:5]=[30,960,544]
            n['widgets_values'][0]='A quiet late-night diner after closing. A tired waitress wipes the counter while rain trails down the front window. The camera slowly pushes toward the empty booth as the neon sign hums outside. No music.'
            if len(n['widgets_values'])>12: n['widgets_values'][12]='gemma4_e2b_it_int8_convrot.safetensors'
        if n.get('type')=='ResolutionSelector' and len(n.get('widgets_values',[]))>1: n['widgets_values'][1]=0.5
        if n.get('type')=='MarkdownNote' and n.get('widgets_values'):
            note=n['widgets_values'][0]
            if n.get('id')==407:
                note += "\n\n## ACDEV filmmaker controls\n\nThis workflow starts from a scene prompt and has no image input. The default is 30 seconds at 24 fps (721 frames) and 0.5 MP. This long duration is not GPU-validated; reduce length if VRAM or runtime is insufficient."
                n['widgets_values'][0]=note
    for sub in t2v.get('definitions',{}).get('subgraphs',[]):
        for n in sub.get('nodes',[]):
            title=(n.get('title') or '').lower()
            if 'duration' in title and n.get('widgets_values') and isinstance(n['widgets_values'][0],(int,float)): n['widgets_values'][0]=30
            if title=='width' and n.get('widgets_values'): n['widgets_values'][0]=960
            if title in ('height','height (pixels)') and n.get('widgets_values'): n['widgets_values'][0]=544
            if 'enable prompt enhance' in title and n.get('widgets_values'): n['widgets_values'][0]=False
    expose_negative_prompt(t2v,405,373)
    use_conv_video_vae(t2v); write('02_LTX25_Text_to_Video.json',t2v)

    flf=read(REF/'video_ltx2_5_flf2v.json'); rename(flf,'First and Last Frame — Filmmaker')
    set_duration(flf)
    for n in flf['nodes']:
        if n.get('type')=='LoadImage':
            n['widgets_values']=['','image']
            n['title']='Opening Frame' if n['id']==31 else 'Closing Frame'
        if n.get('id')==251:
            n['title']='First and Last Frame — Filmmaker Controls'
            if len(n.get('widgets_values',[]))>4: n['widgets_values'][2:5]=[30,960,544]
            if len(n.get('widgets_values',[]))>1: n['widgets_values'][1]=False
    for sg in flf.get('definitions',{}).get('subgraphs',[]):
        for n in sg.get('nodes',[]):
            if n.get('type')=='PrimitiveInt' and (n.get('title','').lower()=='duration'): n['widgets_values'][0]=30
            if n.get('type')=='PrimitiveInt' and n.get('title','').lower()=='width': n['widgets_values'][0]=960
            if n.get('type')=='PrimitiveInt' and n.get('title','').lower()=='height': n['widgets_values'][0]=544
            if n.get('type')=='PrimitiveBoolean' and 'prompt enhance' in n.get('title','').lower(): n['widgets_values']=[False]
    expose_negative_prompt(flf,251,217)
    use_conv_video_vae(flf); write('03_LTX25_First_Last_Frame.json',flf)

    a2v=read(REF/'LTX-2.5_A2V_Two_Stage_Distilled.json'); rename(a2v,'Audio to Video — Filmmaker'); set_duration(a2v); use_default_prompt_enhancer(a2v); use_int8_stack(a2v)
    for n in a2v['nodes']:
        if n.get('type')=='LoadImage': n['widgets_values']=['','image']; n['title']='Optional Opening Frame'
        if n.get('type')=='LoadAudio': n['title']='Source Audio — Preserved in Final Video'
        if n.get('id')==5512 and n.get('widgets_values'): n['widgets_values'][0]=30
        if n.get('id')==2004: n['title']='Optional Opening Frame'
    use_conv_video_vae(a2v); write('04_LTX25_Audio_to_Video.json',a2v)

    t2a=read(REF/'LTX-2.5_T2A_Single_Stage_Distilled.json'); rename(t2a,'Text to Audio — Sound Designer'); set_duration(t2a); use_default_prompt_enhancer(t2a); use_int8_stack(t2a)
    # The upstream nested graph has two root links aimed at the wrong input
    # slots: the text encoder is sent to ckpt_path, and the enhancer to
    # text_encoder. Keep the visible input declarations and actual links in
    # sync so ComfyUI receives a checkpoint path plus both CLIP objects.
    for link in t2a.get('links',[]):
        if link[0]==13811:  # Load Models: text_encoder -> Input Parameters
            link[4]=8
        elif link[0]==4:  # Load Models: text_enhancer -> Input Parameters
            link[4]=9
    for n in t2a['nodes']:
        if n.get('type')=='PrimitiveFloat' and 'duration' in (n.get('title') or '').lower() and n.get('widgets_values'): n['widgets_values'][0]=30
    write('05_LTX25_Text_to_Audio.json',t2a)

    advanced=copy.deepcopy(master); rename(advanced,'Two Stage Generation — Advanced Filmmaker'); set_duration(advanced)
    for n in advanced['nodes']:
        if n.get('type')=='LoadImage': n['widgets_values']=['','image']; n['title']='Opening Image'
        if n.get('id')==398: n['title']='Two Stage Generation — Advanced Filmmaker Controls'
        if n.get('type')=='ResolutionSelector' and len(n.get('widgets_values',[]))>1: n['widgets_values'][1]=0.5
    use_conv_video_vae(advanced); write('06_LTX25_Two_Stage_Advanced.json',advanced)

    ing=read(REF/'LTX-2.5_ICLoRA_Ingredients_Single_Stage_Distilled.json'); rename(ing,'Ingredients — Character and Scene Continuity')
    for n in ing['nodes']:
        if n.get('type')=='LoadImage': n['widgets_values']=['','image']; n['title']='Reference Characters and Objects'
        if n.get('id')==9008 and n.get('widgets_values'): n['widgets_values'][0]=5
        if n.get('id')==5004 and len(n.get('widgets_values',[]))>5:
            n['widgets_values'][4]='ltx-2.5-22b-ic-lora-ingredients-0.9.safetensors'; n['widgets_values'][5]=1.0
        if n.get('id')==5508:
            n['title']='Who Is in This Scene? / What Happens in This Shot?'
            n['widgets_values'][0]='Reference sheet: [describe the characters, props, wardrobe, and setting by their positions in the sheet.]\n\nGenerated video: [describe the action, camera movement, and sound.]'
        if n.get('id')==5529 and n.get('widgets_values'):
            n['widgets_values'][0]="## Rendering Quality\n\nIngredients is a single-stage distilled workflow. The published training bucket is 768 × 448 at 121 frames and 24 fps (about five seconds). Longer clips are out of distribution; keep this control explicit and test shorter segments for production continuity."
        if n.get('id')==2004: n['title']='Reference Characters and Objects'
        if n.get('id')==5527 and n.get('widgets_values'):
            n['widgets_values'][0] = "## Ingredients — Character and Scene Continuity\n\nUpload one reference sheet containing characters, props, wardrobe or locations. Describe the visible elements by position in the sheet. The reference sheet is repeated as an IC-LoRA guide through the full clip; it is not automatically the first frame.\n\n**Who Is in This Scene?** Describe the cast and identify each person by their position on the reference sheet.\n\n**What Happens in This Shot?** Describe the action, camera movement, and sound. Keep the same character and costume descriptions across separate clips.\n\nThe Ingredients IC-LoRA uses the dedicated guide-conditioning graph. This is a single-stage workflow."
        if n.get('id')==5526 and n.get('widgets_values'):
            n['widgets_values'][0]="## Ingredients model limits\n\nThe adapter was trained around 768 × 448, 121 frames, and 24 fps. It expects a reference sheet repeated through the clip and the two-part prompt format: `Reference sheet: ...` followed by `Generated video: ...`. Longer durations or other sizes are out of distribution. The node graph here supplies the guide frames, crops them after sampling, and loads the dedicated adapter."
    # Keep the official training bucket as the visible default for this specialized adapter.
    for sub in ing.get('definitions',{}).get('subgraphs',[]):
        for n in sub.get('nodes',[]):
            if n.get('id')==9008 and n.get('widgets_values'): n['widgets_values'][0]=5
            if n.get('id')==4988 and n.get('type')=='PrimitiveInt': n['widgets_values'][0]=121
            if n.get('id')==5605 and n.get('widgets_values'): n['widgets_values'][0]='gemma4-12b-with-proj-ltx-2.5-bf16.safetensors'
            if n.get('type')=='LTXVLoader' and n.get('widgets_values'):
                n['widgets_values']=[('ltx-2.5-22b-distilled-transformer-bf16.safetensors' if isinstance(v,str) and 'ltx-2.5' in v and 'transformer' in v else v) for v in n['widgets_values']]
            if n.get('type')=='LTXICLoRALoaderModelOnly' and len(n.get('widgets_values',[]))>1:
                n['widgets_values'][0]='ltx-2.5-22b-ic-lora-ingredients-0.9.safetensors'; n['widgets_values'][1]=1.0
            if n.get('id')==5602 and n.get('type')=='UNETLoader' and n.get('widgets_values'):
                n['widgets_values'][0]='ltx-2.5-22b-distilled-transformer-bf16.safetensors'
            if n.get('type')=='PrimitiveFloat' and 'duration' in (n.get('title') or '').lower() and n.get('widgets_values'): n['widgets_values'][0]=5
            if n.get('type')=='PrimitiveInt' and (n.get('title') or '').lower()=='width' and n.get('widgets_values'): n['widgets_values'][0]=768
            if n.get('type')=='PrimitiveInt' and (n.get('title') or '').lower()=='height' and n.get('widgets_values'): n['widgets_values'][0]=448
    write('07_LTX25_Ingredients.json',ing)

    for direction,name,title,prompt_title,edge,result in (
        ('after','08_LTX25_Extend_After.json','Extend Video — Continue After Your Clip','What Happens Next','ending','your whole clip followed by the new section'),
        ('before','09_LTX25_Extend_Before.json','Extend Video — Lead In Before Your Clip','What Happens Before','opening','the new section followed by your whole clip')):
        ext=read(V2V/f'extend_{direction}.json'); rename(ext,title)
        add_note(ext,'How to Extend a Clip',EXTEND_NOTE.format(direction=direction,prompt_title=prompt_title,edge=edge,result=result))
        write(name,ext)

    angle=read(V2V/'new_angle.json'); rename(angle,'New Angle — Coverage Locked to Your Clip\'s Sound')
    add_note(angle,'How to Shoot a New Angle',NEW_ANGLE_NOTE)
    write('10_LTX25_New_Angle.json',angle)

if __name__=='__main__': main()
