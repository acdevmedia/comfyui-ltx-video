#!/usr/bin/env python3
"""Fill in the SHA256 of licence-gated files, which Hugging Face only shows to an account that accepted them.

Maintainer tool, run on a workstation. Reads HF_TOKEN from the shell or the ignored .env and never prints
it. Revision and size are already pinned; this writes the hash each entry is missing and verifies the rest.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];PROFILE=ROOT/'versions/ltx-2.5/config/models.json'

def token():
    if os.getenv('HF_TOKEN'):return os.environ['HF_TOKEN'].strip()
    if (ROOT/'.env').exists():
        for line in (ROOT/'.env').read_text().splitlines():
            if line.startswith('HF_TOKEN='):return line.split('=',1)[1].strip().strip('\'"')
    raise SystemExit('HF_TOKEN is missing; set it in the shell or the ignored .env.')

def lfs_hash(entry,key):
    url=f'https://huggingface.co/api/models/{entry["repo"]}/paths-info/{entry["revision"]}'
    body=urllib.parse.urlencode({'paths':entry['file']}).encode()
    request=urllib.request.Request(url,data=body,headers={'Authorization':'Bearer '+key})
    try:
        with urllib.request.urlopen(request,timeout=60) as response:item=json.load(response)[0]
    except urllib.error.HTTPError as error:
        raise SystemExit(f'Hugging Face refused {entry["repo"]} (HTTP {error.code}). Accept its licence with this account, then run this again.')
    if item.get('size')!=entry['size']:raise SystemExit(f'{entry["file"]}: size changed upstream; check the pinned revision.')
    digest=item['lfs']['oid']
    if len(digest)!=64 or set(digest)=={'*'}:raise SystemExit(f'{entry["repo"]}: Hugging Face hid the hash. Accept its licence with this account, then run this again.')
    return digest

text=PROFILE.read_text();data=json.loads(text);key=token();changed=0
for entry in data['models']:
    if not entry.get('gated'):continue
    digest=lfs_hash(entry,key)
    if entry['sha256'] not in (None,digest):raise SystemExit(f'{entry["file"]}: pinned SHA256 differs from Hugging Face.')
    # One model per line in this file, so only the hash changes.
    if entry['sha256'] is None:text=text.replace(f'"size":{entry["size"]},"sha256":null',f'"size":{entry["size"]},"sha256":"{digest}"');changed+=1
    print('[pin]',entry['file'],digest)
PROFILE.write_text(text)
print(f'[pin] {changed} hash(es) added to {PROFILE.relative_to(ROOT)}.')
