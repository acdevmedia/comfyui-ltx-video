#!/usr/bin/env python3
"""Build filmmaker-named workflow assets from the preserved master and official graph refs."""
import copy, json, uuid
from api_to_ui import to_ui
from v2v_graphs import PANEL, day_to_night, new_camera_angle, relight
from workflow_panels import fold_into_panel
from workflow_dimensions import apply_dimensions, fit_frame_to_image
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

LTXV_DECODE=[2, 1, 16, 1, False, 'auto', 'auto']

def use_ltxv_tiled_decode(data):
    """Swap core VAEDecodeTiled for LTXVSpatioTemporalTiledVAEDecode (2x2 tiles, 16-latent-frame chunks).

    On an A100 this decoded a 1920x1088x721 conv-VAE latent in 71 s against 126 s, with frame-aligned,
    visually identical output (SSIM 0.98), including across temporal chunk joins.
    """
    graphs=[data]+data.get('definitions',{}).get('subgraphs',[])
    for g in graphs:
        def link_fields(link):
            return (link['id'],link['target_slot']) if isinstance(link,dict) else (link[0],link[4])
        def set_target_slot(link,slot):
            if isinstance(link,dict): link['target_slot']=slot
            else: link[4]=slot
        links={link_fields(l)[0]:l for l in g.get('links',[])}
        dropped=[]
        for n in g.get('nodes',[]):
            if n['type']!='VAEDecodeTiled': continue
            by_name={i['name']:i.get('link') for i in n.get('inputs',[])}
            for name in ('tile_size','overlap','temporal_size','temporal_overlap'):
                if by_name.get(name) is not None: dropped.append(by_name[name])
            for name,slot in (('vae',0),('samples',1)):
                if by_name.get(name) is not None: set_target_slot(links[by_name[name]],slot)
            n['type']='LTXVSpatioTemporalTiledVAEDecode'
            n['inputs']=[{'localized_name':'vae','name':'vae','type':'VAE','link':by_name.get('vae')},
                         {'localized_name':'latents','name':'latents','type':'LATENT','link':by_name.get('samples')}]
            for out in n.get('outputs',[]): out['name']='image'; out['localized_name']='image'
            n['widgets_values']=list(LTXV_DECODE)
            n.setdefault('properties',{})['Node name for S&R']=n['type']
        if not dropped: continue
        # Tile settings that were fed from subgraph inputs no longer exist; remove those inputs too.
        g['links']=[l for l in g['links'] if link_fields(l)[0] not in dropped]
        removed=[]
        for index,inp in enumerate(g.get('inputs',[])):
            inp['linkIds']=[x for x in inp.get('linkIds',[]) if x not in dropped]
            if not inp['linkIds'] and inp['name'] in ('tile_size','overlap','temporal_size','temporal_overlap'): removed.append(index)
        names=[g['inputs'][i]['name'] for i in removed]
        for index in reversed(removed): del g['inputs'][index]
        for l in g['links']:
            origin,slot=(l['origin_id'],l['origin_slot']) if isinstance(l,dict) else (l[1],l[2])
            if origin==-10:
                shift=sum(1 for r in removed if r<slot)
                if isinstance(l,dict): l['origin_slot']-=shift
                else: l[2]-=shift
        for host in graphs:
            for node in host.get('nodes',[]):
                if node['type']!=g.get('id'): continue
                widget_names=[i['name'] for i in node.get('inputs',[]) if i.get('widget')]
                keep=[k for k,name in enumerate(widget_names) if name not in names]
                node['widgets_values']=[node['widgets_values'][k] for k in keep] if len(node.get('widgets_values',[]))==len(widget_names) else node['widgets_values']
                node['inputs']=[i for i in node['inputs'] if i['name'] not in names]

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

TRANSITION='ltx2.3-transition.safetensors'
TRANSITION_LABEL='Transition LoRA strength'

def expose_transition_lora(data, control_id, loader_id):
    """Add the scene transition LoRA after the model loader, off at strength 0, with a panel control.

    Mirrors the control on the LTX-2.3 bundles. It is an LTX-2.3 LoRA, so its effect on 2.5 is unverified.
    """
    control=next(n for n in data['nodes'] if n['id']==control_id)
    sub=next(s for s in data['definitions']['subgraphs'] if s['id']==control['type'])
    loader=next(n for n in sub['nodes'] if n['id']==loader_id)
    out=next(l for l in sub['links'] if l['origin_id']==loader_id)
    target=next(n for n in sub['nodes'] if n['id']==out['target_id'])
    node_id=sub['state']['lastNodeId']+1
    next_link=max([sub['state']['lastLinkId'],data.get('last_link_id',0)]+[l['id'] for l in sub['links']])+1
    model_link,strength_link=next_link,next_link+1
    sub['inputs'].append({'id':str(uuid.uuid5(uuid.NAMESPACE_URL,f"{sub['id']}/transition_strength")),'name':'transition_strength',
        'type':'FLOAT','linkIds':[strength_link],'label':TRANSITION_LABEL,'pos':list(sub['inputs'][-1].get('pos',[0,0]))})
    # The loader's link now ends at the LoRA, and a new link carries the patched model on.
    target['inputs'][out['target_slot']]['link']=model_link
    sub['links'].append({'id':model_link,'origin_id':node_id,'origin_slot':0,'target_id':out['target_id'],'target_slot':out['target_slot'],'type':'MODEL'})
    sub['links'].append({'id':strength_link,'origin_id':-10,'origin_slot':len(sub['inputs'])-1,'target_id':node_id,'target_slot':2,'type':'FLOAT'})
    sub['nodes'].append({'id':node_id,'type':'LoraLoaderModelOnly','pos':[loader['pos'][0],loader['pos'][1]+130],'size':[400,110],'flags':{},'order':loader['order'],'mode':0,
        'inputs':[{'localized_name':'model','name':'model','type':'MODEL','link':out['id']},
                  {'localized_name':'lora_name','name':'lora_name','type':'COMBO','widget':{'name':'lora_name'},'link':None},
                  {'localized_name':'strength_model','name':'strength_model','type':'FLOAT','widget':{'name':'strength_model'},'link':strength_link}],
        'outputs':[{'localized_name':'MODEL','name':'MODEL','type':'MODEL','links':[model_link]}],'title':'Scene Transition LoRA',
        'properties':{'Node name for S&R':'LoraLoaderModelOnly'},'widgets_values':[TRANSITION,0.0]})
    out['target_id'],out['target_slot']=node_id,0
    sub['state'].update(lastNodeId=node_id,lastLinkId=strength_link)
    data['last_link_id']=max(data.get('last_link_id',0),strength_link)
    control['inputs'].append({'label':TRANSITION_LABEL,'name':'transition_strength','type':'FLOAT','widget':{'name':'transition_strength'},'link':None})
    control['widgets_values'].append(0.0)

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

CLIP_SHAPE='''**Width** and **Height** set the frame's area, and your clip sets its shape. **Frames** sets the length, and the shot stops at the end of your clip. Your clip's own sound is kept, so the new shot lines up on the same audio track.'''

DOWNLOAD='''It needs the BF16 stack and this LoRA, which are not in the default download. Run `/opt/ltx25-studio/scripts/download-adapter-models.sh` in the Pod's terminal. Until then it reports a missing model; nothing else is affected.'''

GATED='''**This one needs a licence first.** Accept the terms at [{repo}](https://huggingface.co/{repo}) with the Hugging Face account behind `HF_TOKEN`. '''

CAMERA_NOTE=f'''## How to move the camera

This re-shoots your clip from a new position, like a second camera on the same take. It moves the camera on existing footage, which New Angle (workflow 10) cannot: that one re-stages the moment from a reference sheet.

1. Upload your clip in **Your Clip**.
2. In **The Camera Move**, write only the move, in these exact words:

`crossview. new camera angle: to the left, higher, closer.`

- **Side:** same angle · slightly to the left · slightly to the right · to the left · to the right · far to the left · far to the right
- **Height:** lower · same height · higher
- **Distance:** closer · same distance · further

3. Run. For a big move, feed the result back in and make another small one.

Small moves are the most reliable. The range is about 60° either side of the front, so a view from behind is out of reach. **IC-LoRA Strength** starts at 1.5 because the effect is weaker on fast sampling; 1.2 to 1.5 is the useful range.

{{clip}}

**Not yet proven on LTX-2.5.** This LoRA was trained on LTX-2.3 and no 2.5 build exists, so check a short clip first. It is a v0.9 proof of concept.

{{download}}'''

RELIGHT_NOTE=f'''## How to relight a shot

1. Upload your clip in **Your Clip**. This model was made for sunlit exteriors, and it works best on footage with no strong light direction already, such as an overcast day.
2. Set **Light Direction**. Rotation 0 lights the scene from the camera's side, 90 from the right, 180 from behind and -90 from the left. The ball is added to the corner of the frame the model reads, and is not in the result.
3. In **The Light**, keep the first sentence and match its end to the ball:

`relight the video to match the light-direction ball. hard low-angle sunlight from the right`

- **From:** the front · the front-right · the right · the back-right · behind · the back-left · the left · the front-left
- **Looks:** hard directional sunlight · hard high-angle sunlight · hard low-angle sunlight · soft diffused daylight · soft warm afternoon light · cool soft daylight · dim overcast light · strong backlight with rim light · soft hazy backlight · warm golden low front sun · warm golden low side sun · frontal sunlight

Describe the light only, not the scene, and use one light setup per clip. If the words and the ball disagree, the ball wins. The default ball, elevation 15 at intensity 2, follows Lightricks' example. A higher sun brightens the ball's grey background, so lower **intensity** as you raise **elevation**: about 0.8 at elevation 45. 1280 x 704, 121 frames at 24 fps is what it was trained on, in a single pass.

{{clip}}

**Not yet proven on LTX-2.5.** This LoRA was trained on LTX-2.3 and no 2.5 build exists, so check a short clip first.

{{gated}}{{download}}'''

NIGHT_NOTE=f'''## How to turn day into night

1. Upload a daylight clip at 24 fps in **Your Clip**.
2. In **The Night Look**, describe the night and keep the last sentence, which holds the shot still. Steer the colour with phrases such as warm tungsten light or cool white LED light.
3. Run. Composition, camera and motion come from your clip.

768 x 448, 97 frames at 24 fps is what it was trained on; longer clips drift towards the end.

{{clip}}

{{gated}}{{download}}'''

def ic_lora_workflow(build, name, title, note, note_title):
    """An API graph from v2v_graphs.py folded offline into the one-panel layout, with its how-to note."""
    prompt,layout=build()
    data=to_ui(prompt,title,read(PROFILE_DIR/'config/node-schemas.json')); rename(data,title)
    fields=[{'label':node['_meta']['title'],'source':int(key)} for key,node in prompt.items() if layout[key]==PANEL and node['class_type'].startswith('Primitive')]
    keep=[int(key) for key,node in prompt.items() if node['class_type'] in ('LoadVideo','SphereLightManualNode','SaveVideo')]
    add_note(data,note_title,note)
    fold_into_panel(data,title+' — Filmmaker Controls',keep,fields)
    write(name,data)

A2V_NOTE='''## How to make video from audio

1. Load your soundtrack in **Source Audio**. It is kept exactly as it is in the final video.
2. Optionally load an **Optional Opening Frame** and switch **Use the Opening Frame** on. Without the switch the image is ignored.
3. In **Describe the Video**, say what we see and what happens, timed to the sound.
4. Use **Audio Start** and **Clip Length** to choose the part of the soundtrack to animate.
5. Run. The video is generated to fit the sound and saved with the original audio.

**Rewrite My Prompt with AI** expands a short prompt before generating; it is off by default and adds time. **Width** and **Height** set the first-pass picture size; the second pass upscales it.'''

T2A_NOTE='''## How to make sound from text

1. In **Describe the Sound**, write what should be heard: dialogue, voices, ambience, effects or music.
2. Set **Clip Length** in seconds.
3. Run. Listen in the audio player; the file is saved by **Save Audio** (MP3).

**Rewrite My Prompt with AI** expands a short prompt before generating; it is off by default and adds time. Change **Seed** for a different take of the same prompt.'''

def fold_audio_to_video(data):
    """One controls panel for Audio to Video: soundtrack and opening frame in, video out."""
    note=next(n for n in data['nodes'] if n['id']==5527); note['widgets_values']=[A2V_NOTE]
    next(n for n in data['nodes'] if n['id']==4852)['title']='Save Video'
    fold_into_panel(data,'Audio to Video — Filmmaker Controls',keep=[5600,2004,4852],
        drop_notes=[5528,5529,5530,5531,5532],note_titles={5527:'How to Use Audio to Video'},
        fields=[{'label':'Describe the Video','source':5508},
                {'label':'Negative Prompt (CFG 1.0: little/no effect)','source':5509},
                {'label':'Clip Length (seconds)','source':5512},
                {'label':'Audio Start (seconds)','source':5601},
                {'label':'Frames per Second','source':5511},
                {'label':'Width','kind':'PrimitiveInt','targets':[(5514,'width')]},
                {'label':'Height','kind':'PrimitiveInt','targets':[(5514,'height')]},
                {'label':'Use the Opening Frame','kind':'PrimitiveBoolean','targets':[(5014,'value_3')]},
                {'label':'Rewrite My Prompt with AI','kind':'PrimitiveBoolean','targets':[(5014,'cond')],'value':False},
                {'label':'Seed','kind':'PrimitiveInt','targets':[(5516,'noise_seed'),(5517,'noise_seed')]}])

def fold_text_to_audio(data):
    """One controls panel for Text to Audio: prompt in, audio out plus a player."""
    params=next(n for n in data['nodes'] if n['id']==2)
    # The upstream rewiring left a model filename in enhance_prompt's slot; give the panel clean values.
    widgets=[i['name'] for i in params['inputs'] if i.get('widget')]
    params['widgets_values']=params['widgets_values'][:len(widgets)]
    params['widgets_values'][widgets.index('enhance_prompt')]=False
    note=next(n for n in data['nodes'] if n['id']==15); note['widgets_values']=[T2A_NOTE]
    next(n for n in data['nodes'] if n['id']==5574)['title']='Save Audio (MP3)'
    next(n for n in data['nodes'] if n['id']==12)['title']='Listen'
    fold_into_panel(data,'Text to Audio — Sound Designer Controls',keep=[5574,12],
        drop_notes=[16,17,18,19,20],note_titles={15:'How to Use Text to Audio'},
        fields=[{'label':'Describe the Sound','source':6},
                {'label':'Negative Prompt (CFG 1.0: little/no effect)','source':7},
                {'label':'Clip Length (seconds)','source':11},
                {'label':'Frames per Second','source':10},
                {'label':'Rewrite My Prompt with AI','kind':'PrimitiveBoolean','targets':[(2,'enhance_prompt')]},
                {'label':'Seed','kind':'PrimitiveInt','targets':[(4,'noise_seed')]}])

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
    if any(n.get('title')=='About the Negative Prompt' for n in nodes): return
    anchor=max(nodes,key=lambda n:len(n['widgets_values']) if isinstance(n.get('widgets_values'),list) else 0)
    state=data.get('state') or {}
    node_id=max([n['id'] for n in nodes]+[data.get('last_node_id') or 0,state.get('lastNodeId',0)])+1
    nodes.append({'id':node_id,'type':'MarkdownNote','pos':[min(n['pos'][0] for n in nodes)-560,anchor['pos'][1]],'size':[500,420],
        'flags':{},'order':len(nodes),'mode':0,'inputs':[],'outputs':[],'title':'About the Negative Prompt','properties':{},
        'widgets_values':[NEGATIVE_NOTE],'color':'#222','bgcolor':'#000'})
    if 'last_node_id' in data: data['last_node_id']=node_id
    if 'lastNodeId' in state: state['lastNodeId']=node_id

def link_origin(graph, link_id):
    link=next(l for l in graph['links'] if l['id']==link_id)
    return link['origin_id'],link['origin_slot']

def fit_to_opening_image(name, data):
    """Let the picture a workflow starts from set the frame's shape, so it is used whole."""
    def nested(node_id):
        return next((g,n) for g in data['definitions']['subgraphs'] for n in g['nodes'] if n['id']==node_id)
    def image_of(node):
        return link_origin(graph,next(i for i in node['inputs'] if i['name']=='input')['link'])
    if name[:3] in ('01_','06_'):
        graph,resize=nested(351);switch=next(n for n in graph['nodes'] if n.get('title')=='Switch to Text to Video?')
        fit_frame_to_image(data,graph,372,360,image_of(resize),(switch['id'],0,True))
    elif name[:3]=='03_':
        graph,resize=nested(213)
        fit_frame_to_image(data,graph,215,216,image_of(resize))
    elif name[:3]=='04_':
        graph=nested(6012)[0];slot=next(i for i,x in enumerate(graph['inputs']) if x['name']=='input')
        fit_frame_to_image(data,graph,6012,6013,(-10,slot),(6014,0,False))

def write(name, data):
    apply_dimensions(data,(768,448) if 'Ingredients' in name else None)
    fit_to_opening_image(name,data)
    add_negative_prompt_note(data)
    # Preserve the packaged workflows' random-seed default when rebuilding from
    # older upstream references (including nodes inside controls subgraphs).
    for graph in [data]+data.get('definitions',{}).get('subgraphs',[]):
        for node in graph.get('nodes',[]):
            values=node.get('widgets_values')
            seed_node=node.get('type')=='RandomNoise' or (node.get('type')=='PrimitiveInt' and node.get('title','').lower()=='seed')
            if seed_node and isinstance(values,list):
                for index in range(1,len(values)):
                    if values[index]=='fixed' and isinstance(values[index-1],int):
                        values[index]='randomize'
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
    use_conv_video_vae(i2v); use_ltxv_tiled_decode(i2v); write('01_LTX25_Image_to_Video.json',i2v)

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
    use_conv_video_vae(t2v); use_ltxv_tiled_decode(t2v); write('02_LTX25_Text_to_Video.json',t2v)

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
    expose_transition_lora(flf,251,230)
    use_conv_video_vae(flf); use_ltxv_tiled_decode(flf); write('03_LTX25_First_Last_Frame.json',flf)

    a2v=read(REF/'LTX-2.5_A2V_Two_Stage_Distilled.json'); rename(a2v,'Audio to Video — Filmmaker'); set_duration(a2v); use_default_prompt_enhancer(a2v); use_int8_stack(a2v)
    for n in a2v['nodes']:
        if n.get('type')=='LoadImage': n['widgets_values']=['','image']; n['title']='Optional Opening Frame'
        if n.get('type')=='LoadAudio': n['title']='Source Audio — Preserved in Final Video'
        if n.get('id')==5512 and n.get('widgets_values'): n['widgets_values'][0]=30
        if n.get('id')==2004: n['title']='Optional Opening Frame'
    use_conv_video_vae(a2v); use_ltxv_tiled_decode(a2v); fold_audio_to_video(a2v); write('04_LTX25_Audio_to_Video.json',a2v)

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
    fold_text_to_audio(t2a); write('05_LTX25_Text_to_Audio.json',t2a)

    advanced=copy.deepcopy(master); rename(advanced,'Two Stage Generation — Advanced Filmmaker'); set_duration(advanced)
    for n in advanced['nodes']:
        if n.get('type')=='LoadImage': n['widgets_values']=['','image']; n['title']='Opening Image'
        if n.get('id')==398: n['title']='Two Stage Generation — Advanced Filmmaker Controls'
        if n.get('type')=='ResolutionSelector' and len(n.get('widgets_values',[]))>1: n['widgets_values'][1]=0.5
    use_conv_video_vae(advanced); use_ltxv_tiled_decode(advanced); write('06_LTX25_Two_Stage_Advanced.json',advanced)

    # One-panel layout built in ComfyUI's frontend from the earlier official-graph adaptation (reference sheet,
    # 121-frame bucket, BF16 stack and notes are baked in); see docs/workflows.md.
    ing=read(V2V/'ingredients.json'); rename(ing,'Ingredients — Character and Scene Continuity')
    write('07_LTX25_Ingredients.json',ing)

    for direction,name,title,prompt_title,edge,result in (
        ('after','08_LTX25_Extend_After.json','Extend Video — Continue After Your Clip','What Happens Next','ending','your whole clip followed by the new section'),
        ('before','09_LTX25_Extend_Before.json','Extend Video — Lead In Before Your Clip','What Happens Before','opening','the new section followed by your whole clip')):
        ext=read(V2V/f'extend_{direction}.json'); rename(ext,title)
        use_ltxv_tiled_decode(ext)
        add_note(ext,'How to Extend a Clip',EXTEND_NOTE.format(direction=direction,prompt_title=prompt_title,edge=edge,result=result))
        write(name,ext)

    angle=read(V2V/'new_angle.json'); rename(angle,'New Angle — Coverage Locked to Your Clip\'s Sound')
    add_note(angle,'How to Shoot a New Angle',NEW_ANGLE_NOTE)
    write('10_LTX25_New_Angle.json',angle)

    relight_repo='Lightricks/LTX-2.3-22b-IC-LoRA-Relight'; night_repo='Lightricks/LTX-2.5-22b-IC-LoRA-Day-To-Night'
    ic_lora_workflow(new_camera_angle,'11_LTX25_New_Camera_Angle.json','New Camera Angle',CAMERA_NOTE.format(clip=CLIP_SHAPE,download=DOWNLOAD),'How to Move the Camera')
    ic_lora_workflow(relight,'12_LTX25_Relight.json','Relight',RELIGHT_NOTE.format(clip=CLIP_SHAPE,gated=GATED.format(repo=relight_repo),download=DOWNLOAD),'How to Relight a Shot')
    ic_lora_workflow(day_to_night,'13_LTX25_Day_to_Night.json','Day to Night',NIGHT_NOTE.format(clip=CLIP_SHAPE,gated=GATED.format(repo=night_repo),download=DOWNLOAD),'How to Turn Day into Night')

if __name__=='__main__': main()
