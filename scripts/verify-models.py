#!/usr/bin/env python3
import argparse, json, os, sys
from pathlib import Path
parser=argparse.ArgumentParser(); parser.add_argument('--required',action='store_true'); args=parser.parse_args()
root=Path(os.environ.get('COMFYUI_DIR','/workspace/ComfyUI'))/'models'; manifest=Path(os.environ.get('MODEL_MANIFEST','/opt/ltx25-studio/versions/ltx-2.5/config/models.json'))
missing=[]
for m in json.loads(manifest.read_text())['models']:
    if not m.get('default'): continue
    if m['id']=='ingredients-ic-lora' and os.environ.get('AUTO_DOWNLOAD_ADAPTERS','true').lower() not in {'1','true','yes'}: continue
    p=root/m.get('target',m['file'])
    if p.is_file() and p.stat().st_size: print(f"[models] OK {m['id']} ({p.stat().st_size/1024**3:.2f} GiB)")
    else: print(f'[models] MISSING {m["id"]}: {p}'); missing.append(p)
if missing and args.required: print('[models] Set HF_TOKEN and accept gated model terms, or check provisioning logs.',file=sys.stderr)
raise SystemExit(bool(missing))
