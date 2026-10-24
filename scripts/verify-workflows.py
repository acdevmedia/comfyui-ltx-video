#!/usr/bin/env python3
import argparse, json, os, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VERSION=os.environ.get('LTX_VERSION','ltx-2.5')
PROFILE_DIR=ROOT/'versions'/VERSION
PROFILE=json.loads((PROFILE_DIR/'profile.json').read_text())
REQUIRED=PROFILE['assets']['workflow_files']
parser=argparse.ArgumentParser(); parser.add_argument('--installed',action='store_true'); args=parser.parse_args()
base=Path('/workspace/ComfyUI/user/default/workflows') if args.installed else PROFILE_DIR/PROFILE['assets']['workflows']; errors=[]
for name in REQUIRED:
    p=base/name
    if not p.is_file(): errors.append(f'missing {p}'); continue
    try:
        d=json.loads(p.read_text())
        if not isinstance(d.get('nodes'),list) or not d['nodes']: errors.append(f'{name}: graph has no nodes')
        if not isinstance(d.get('links'),list): errors.append(f'{name}: links are missing')
        last_id=d.get('last_node_id') or d.get('state',{}).get('lastNodeId')
        if last_id is not None and last_id<=0: errors.append(f'{name}: invalid last_node_id')
    except Exception as e: errors.append(f'{name}: invalid JSON ({type(e).__name__})')
if errors: print('\n'.join('[workflow] ERROR '+x for x in errors),file=sys.stderr); raise SystemExit(1)
print(f'[workflow] Valid JSON and graph structure for all {len(REQUIRED)} filmmaker workflows in {base}')
