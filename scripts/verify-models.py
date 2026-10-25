#!/usr/bin/env python3
import argparse, json, os, sys
from pathlib import Path
parser=argparse.ArgumentParser(); parser.add_argument('--required',action='store_true'); parser.add_argument('--group',choices=('default','ingredients','optional','all'),default='default'); args=parser.parse_args()
root=Path(os.environ.get('COMFYUI_DIR','/workspace/ComfyUI'))/'models'; manifest=Path(os.environ.get('MODEL_MANIFEST','/opt/ltx25-studio/versions/ltx-2.5/config/models.json'))
missing=[]
for m in json.loads(manifest.read_text())['models']:
    group=m.get('group','core')
    if args.group=='default' and (not m.get('default') or m.get('optional')): continue
    if args.group!='all' and args.group!='default' and group!=args.group: continue
    if args.group=='default' and group=='ingredients' and os.environ.get('AUTO_DOWNLOAD_ADAPTERS','false').lower() not in {'1','true','yes'}: continue
    p=root/m.get('target',m['file'])
    if p.is_file() and p.stat().st_size: print(f"[models] OK {m['id']} ({p.stat().st_size/1024**3:.2f} GiB)")
    else: print(f'[models] MISSING {m["id"]}: {p}'); missing.append(p)
if missing and args.required: print('[models] Create RunPod Secret HUGGINGFACE_TOKEN and accept gated model terms, or check provisioning logs.',file=sys.stderr)
raise SystemExit(bool(missing))
