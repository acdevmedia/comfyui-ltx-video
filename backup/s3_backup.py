#!/usr/bin/env python3
"""Non-deleting S3-compatible output backup with stable-file checks and restart state."""
import json, mimetypes, os, queue, sys, threading, time, uuid
from pathlib import Path
from urllib.parse import quote

SOURCE=Path(os.environ.get('BACKUP_SOURCE_DIR','/workspace/ComfyUI/output'))
STATE=Path('/workspace/.ltx25-studio/backup')
ALLOWED={'.mp4','.wav','.flac','.mp3','.m4a','.json'}

def log(message): print(f"[backup] {time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())} {message}",flush=True)
def truthy(value): return str(value or '').strip().lower() in {'1','true','yes','on'}

class Config:
    def __init__(self):
        self.endpoint=os.getenv('S3_ENDPOINT_URL','').strip() or None
        self.bucket=os.getenv('S3_BUCKET','').strip()
        self.region=os.getenv('S3_REGION','').strip() or 'sfo3'
        self.prefix=(os.getenv('S3_PREFIX','').strip() or 'ltx25-studio').strip('/')
        self.path_style=truthy(os.getenv('S3_FORCE_PATH_STYLE','false'))
        self.storage_class=os.getenv('S3_STORAGE_CLASS','').strip()
        self.sse=os.getenv('S3_SSE','').strip()
        self.settle=max(0,int(os.getenv('BACKUP_SETTLE_SECONDS','8')))
        self.recheck=max(10,int(os.getenv('BACKUP_RECHECK_SECONDS','120')))
        self.session_token=os.getenv('S3_SESSION_TOKEN','').strip()
        if self.session_token.startswith('OPTIONAL_'): self.session_token=''
        self.access=os.getenv('S3_ACCESS_KEY_ID','').strip()
        self.secret=os.getenv('S3_SECRET_ACCESS_KEY','').strip()
        missing=[]
        if not self.bucket or self.bucket.startswith('YOUR_'): missing.append('S3_BUCKET')
        if (self.access.startswith('YOUR_') or not self.access) != (self.secret.startswith('YOUR_') or not self.secret): missing.append('both S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY')
        if missing: raise ValueError('missing/invalid configuration: '+', '.join(missing))

    def client(self):
        import boto3
        from botocore.config import Config as BotoConfig
        if self.access and self.secret and not self.access.startswith('YOUR_') and not self.secret.startswith('YOUR_'):
            session=boto3.Session(aws_access_key_id=self.access,aws_secret_access_key=self.secret,aws_session_token=self.session_token or None,region_name=self.region)
        else:
            session=boto3.Session(region_name=self.region)
        creds=session.get_credentials()
        if not creds and self.endpoint:
            raise ValueError('S3 access key credentials are missing for the configured custom endpoint.')
        if not creds and not self.endpoint:
            log('No explicit keys found; using the AWS SDK credential chain (instance role, web identity, or profile).')
        return session.client('s3',endpoint_url=self.endpoint,region_name=self.region,config=BotoConfig(s3={'addressing_style':'path' if self.path_style else 'auto'}))

    def extra_args(self,path):
        args={'ContentType':mimetypes.guess_type(path.name)[0] or 'application/octet-stream'}
        if self.storage_class: args['StorageClass']=self.storage_class
        if self.sse and self.sse.lower() not in {'none','disabled','false'}:
            args['ServerSideEncryption']=self.sse
            if self.sse.upper().startswith('AWS:KMS:'): args['SSEKMSKeyId']=self.sse.split(':',2)[2]
        return args

def valid_file(path):
    if not path.is_file() or path.suffix.lower() not in ALLOWED: return False
    if any(part.startswith('.') or part.lower() in {'temp','tmp','intermediate','latents'} for part in path.parts): return False
    return not path.name.lower().endswith(('.tmp','.part','.partial','.incomplete'))

def fingerprint(path):
    s=path.stat(); return f'{s.st_size}:{s.st_mtime_ns}'

def settled(path, seconds):
    try:
        first=fingerprint(path)
        if seconds: time.sleep(seconds)
        second=fingerprint(path)
        if first!=second: return False
        if path.stat().st_size==0: return False
        return True
    except (FileNotFoundError,PermissionError,OSError): return False

def instance_id():
    STATE.mkdir(parents=True,exist_ok=True)
    p=STATE/'instance-id'
    if not p.exists():
        tmp=p.with_suffix('.tmp'); tmp.write_text(uuid.uuid4().hex+'\n'); os.chmod(tmp,0o600); os.replace(tmp,p)
    return p.read_text().strip()

def load_state():
    try: return json.loads((STATE/'uploaded.json').read_text())
    except (FileNotFoundError,json.JSONDecodeError): return {}

def save_state(state):
    p=STATE/'uploaded.json'; tmp=p.with_suffix('.tmp'); tmp.write_text(json.dumps(state,sort_keys=True)); os.chmod(tmp,0o600); os.replace(tmp,p)

def key_for(prefix, ident, path):
    rel=path.relative_to(SOURCE).as_posix()
    if path.suffix.lower()=='.mp4': category='video'
    elif path.suffix.lower() in {'.wav','.flac','.mp3','.m4a'}: category='audio'
    else: category='metadata'
    return '/'.join(x for x in (prefix,ident,category,rel) if x)

def upload_one(client,cfg,path,ident,state,force=False):
    if not valid_file(path): return False
    try:
        if not settled(path,cfg.settle): return False
        mark=fingerprint(path); rel=path.relative_to(SOURCE).as_posix()
        if not force and state.get(rel)==mark: return True
        key=key_for(cfg.prefix,ident,path)
        client.upload_file(str(path),cfg.bucket,key,ExtraArgs=cfg.extra_args(path))
        if fingerprint(path)!=mark:
            log(f'File changed during upload; will retry: {rel}')
            return False
        state[rel]=mark; save_state(state); log(f'Uploaded s3://{cfg.bucket}/{key} ({mark.split(":",1)[0]} bytes)')
        return True
    except Exception as exc:
        log(f'Upload failed for {path.name}: {type(exc).__name__}; will retry during reconciliation.')
        return False

def eligible():
    if not SOURCE.exists(): return []
    return [p for p in SOURCE.rglob('*') if valid_file(p)]

def once():
    cfg=Config(); client=cfg.client(); ident=uuid.uuid4().hex
    files=eligible()
    if not files: log(f'No completed outputs found under {SOURCE}'); return 0
    state={}; failed=[]
    for path in files:
        if not upload_one(client,cfg,path,ident,state): failed.append(path)
    log(f'Manual backup finished: {len(files)-len(failed)} uploaded, {len(failed)} failed; prefix={cfg.prefix}/{ident}')
    return int(bool(failed))

def verify():
    cfg=Config(); client=cfg.client(); key='/'.join(x for x in (cfg.prefix,'_verification',uuid.uuid4().hex+'.txt') if x)
    body=b'ACDEV LTX-2.5 Studio S3 backup verification\n'
    client.put_object(Bucket=cfg.bucket,Key=key,Body=body,ContentType='text/plain')
    log(f'Upload permission verified for s3://{cfg.bucket}/{key}')
    try:
        client.delete_object(Bucket=cfg.bucket,Key=key)
        log('Test object removed. Delete permission is optional for normal backups.')
    except Exception:
        log('Test object could not be removed; delete permission is optional, and the tiny test object remains.')
    return 0

def watch():
    cfg=Config(); client=cfg.client(); ident=instance_id(); state=load_state()
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
    events=queue.Queue()
    class Handler(FileSystemEventHandler):
        def on_closed(self,e):
            if not e.is_directory: events.put(Path(e.src_path))
        def on_moved(self,e):
            if not e.is_directory: events.put(Path(e.dest_path))
        def on_created(self,e):
            if not e.is_directory: events.put(Path(e.src_path))
    SOURCE.mkdir(parents=True,exist_ok=True)
    observer=Observer(); observer.schedule(Handler(),str(SOURCE),recursive=True); observer.start()
    log(f'Watching {SOURCE} -> s3://{cfg.bucket}/{cfg.prefix}/{ident}/ (non-deleting)')
    next_scan=0
    try:
        while True:
            now=time.monotonic()
            if now>=next_scan:
                for p in eligible(): events.put(p)
                next_scan=now+cfg.recheck
            try: path=events.get(timeout=1)
            except queue.Empty: continue
            if path.exists(): upload_one(client,cfg,path,ident,state)
    finally:
        observer.stop(); observer.join(timeout=5)

def main():
    mode=sys.argv[1] if len(sys.argv)>1 else 'watch'
    try:
        if mode=='watch': watch()
        elif mode=='once': return once()
        elif mode=='verify': return verify()
        else: print('Usage: s3_backup.py watch|once|verify',file=sys.stderr); return 2
    except KeyboardInterrupt: return 0
    except Exception as exc:
        log(f'ERROR: {type(exc).__name__}: {exc}')
        return 1
    return 0

if __name__=='__main__': raise SystemExit(main())
