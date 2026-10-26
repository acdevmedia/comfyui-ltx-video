#!/usr/bin/env python3
"""Seed packaged workflows without overwriting persistent user files."""
import json, math, os, shutil
from pathlib import Path

APP=Path(os.environ.get('LTX_APP_DIR','/opt/ltx25-studio'))
VERSION=os.environ.get('LTX_VERSION','ltx-2.5')
PROFILE_DIR=APP/'versions'/VERSION
PROFILE=json.loads((PROFILE_DIR/'profile.json').read_text())
SOURCE=PROFILE_DIR/PROFILE['assets']['workflows']
ROOT=Path(os.environ.get('COMFYUI_DIR','/workspace/ComfyUI'))
DEST=ROOT/'user/default/workflows'
NAMES=PROFILE['assets']['workflow_files']
ASPECTS={'16:9':'16:9 (Widescreen)','9:16':'9:16 (Portrait)','4:3':'4:3','1:1':'1:1','21:9':'21:9'}

def dimensions(megapixels, aspect):
    ratio=float(aspect.split(':')[0])/float(aspect.split(':')[1])
    pixels=max(0.2,min(2.0,float(megapixels)))*1_000_000
    return max(320,round(math.sqrt(pixels*ratio)/32)*32),max(320,round(math.sqrt(pixels/ratio)/32)*32)

def set_panel_field(data, label, value):
    """Set a labelled field on a workflow's controls panel (a subgraph node on the canvas)."""
    for n in data.get('nodes',[]):
        fields=[i for i in n.get('inputs',[]) if i.get('widget')]
        for index,field in enumerate(fields):
            if field.get('label')==label and len(n.get('widgets_values') or [])==len(fields):
                n['widgets_values'][index]=value
                return True
    return False

def customize(name, data):
    duration=float(os.getenv('LTX_DEFAULT_DURATION','30')); fps=int(os.getenv('LTX_DEFAULT_FPS','24'))
    mp=float(os.getenv('LTX_DEFAULT_MEGAPIXELS','0.5')); aspect=os.getenv('LTX_DEFAULT_ASPECT_RATIO','16:9')
    if aspect not in ASPECTS: raise ValueError(f'Unsupported LTX_DEFAULT_ASPECT_RATIO={aspect}; use one of {", ".join(ASPECTS)}.')
    width,height=dimensions(mp,aspect)
    # Node ids are only unique within one graph, so each id rule is scoped to the workflow it was written for.
    prefix=name[:3]
    for n in data.get('nodes',[]):
        nid=n.get('id'); typ=n.get('type'); values=n.get('widgets_values',[])
        if typ=='ResolutionSelector' and len(values)>=2: values[0]=ASPECTS[aspect]; values[1]=mp
        if (prefix,nid) in (('01_',398),('06_',398),('02_',405),('03_',251)):
            if len(values)>2: values[2]=duration
            if len(values)>4: values[3:5]=[width,height]
            if nid in (405,251) and len(values)>6: values[6]=fps
    if prefix in ('04_','05_'):
        set_panel_field(data,'Frames per Second',fps)
        set_panel_field(data,'Clip Length (seconds)',duration)
    if prefix=='04_':
        set_panel_field(data,'Width',width)
        set_panel_field(data,'Height',height)
    if name.startswith('07_'):
        print('[workflows] Ingredients keeps its five-second / 121-frame training-bucket default despite generic duration settings.')
    return data

def main():
    DEST.mkdir(parents=True,exist_ok=True)
    for name in NAMES:
        target=DEST/name
        if target.exists():
            print(f'[workflows] Preserving existing workflow: {name}')
            continue
        source=SOURCE/name
        if not source.is_file(): raise FileNotFoundError(f'Packaged workflow missing: {source}')
        target.write_text(json.dumps(customize(name,json.loads(source.read_text())),indent=2,ensure_ascii=False)+'\n')
        print(f'[workflows] Installed {name}')
    selected=os.getenv('LTX_DEFAULT_WORKFLOW',PROFILE['default_workflow']).removesuffix('.json')+'.json'
    if selected not in NAMES: raise ValueError(f'Unknown LTX_DEFAULT_WORKFLOW={selected}; choose one of the packaged workflow names.')
    default_template=APP/'ComfyUI/web/templates/default.json'
    default_template.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(DEST/selected,default_template)
    print(f'[workflows] Default ComfyUI graph: {selected}')

if __name__=='__main__': main()
