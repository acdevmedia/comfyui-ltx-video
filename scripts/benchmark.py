#!/usr/bin/env python3
import argparse, json, os, statistics, subprocess, threading, time, urllib.request, uuid
from pathlib import Path

def request(url, data=None):
    body=None if data is None else json.dumps(data).encode()
    req=urllib.request.Request(url,data=body,headers={'Content-Type':'application/json'} if body else {})
    with urllib.request.urlopen(req,timeout=30) as r: return json.loads(r.read())

def gpu_stats():
    row=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,memory.used','--format=csv,noheader,nounits'],text=True).strip().splitlines()[0]
    name,total,used=[v.strip() for v in row.split(',',2)]; return name,int(total),int(used)

def main():
    p=argparse.ArgumentParser(description='Measure one reproducible ComfyUI API workflow run.')
    p.add_argument('--api',default='http://127.0.0.1:8188'); p.add_argument('--workflow',required=True,help='Workflow name / version label')
    p.add_argument('--resolution',required=True,help='WidthxHeight label, e.g. 960x544'); p.add_argument('--frames',type=int,required=True)
    p.add_argument('--prompt-json',required=True,help='ComfyUI API-format prompt JSON exported from the workflow')
    p.add_argument('--gpu-rate-usd-hour',type=float); p.add_argument('--output',default='/workspace/logs/benchmarks.jsonl')
    a=p.parse_args(); base=a.api.rstrip('/'); prompt=json.loads(Path(a.prompt_json).read_text())
    if 'prompt' in prompt and isinstance(prompt['prompt'],dict): prompt=prompt['prompt']
    gpu,total,used=gpu_stats(); peaks=[used]; stop=threading.Event()
    def monitor():
        while not stop.wait(.5):
            try: peaks.append(gpu_stats()[2])
            except Exception: pass
    watcher=threading.Thread(target=monitor,daemon=True); watcher.start()
    start=time.monotonic(); queued=request(base+'/prompt',{'prompt':prompt,'client_id':str(uuid.uuid4())}); pid=queued['prompt_id']
    while True:
        time.sleep(3); history=request(base+'/history/'+pid)
        entry=history.get(pid,{})
        if entry and ('outputs' in entry or entry.get('status',{}).get('completed')): break
    elapsed=time.monotonic()-start; stop.set(); watcher.join(timeout=1)
    result={'timestamp_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'gpu':gpu,'workflow':a.workflow,'resolution':a.resolution,'frames':a.frames,'generation_seconds':round(elapsed,2),'peak_gpu_memory_mib':max(peaks),'frames_per_second':round(a.frames/elapsed,3),'prompt_id':pid}
    if a.gpu_rate_usd_hour is not None: result['estimated_cost_usd']=round(elapsed/3600*a.gpu_rate_usd_hour,4)
    out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('a') as f: f.write(json.dumps(result)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
