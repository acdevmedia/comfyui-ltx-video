#!/usr/bin/env python3
import argparse, asyncio, json, random, subprocess, threading, time, urllib.request, uuid
from pathlib import Path

def request(url, data=None):
    body=None if data is None else json.dumps(data).encode()
    req=urllib.request.Request(url,data=body,headers={'Content-Type':'application/json'} if body else {})
    with urllib.request.urlopen(req,timeout=30) as r:
        raw=r.read()
        return json.loads(raw) if raw.strip() else {}

def gpu_stats():
    row=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,memory.used','--format=csv,noheader,nounits'],text=True).strip().splitlines()[0]
    name,total,used=[v.strip() for v in row.split(',',2)]; return name,int(total),int(used)

def stage_of(class_type):
    """Coarse pipeline phase for a node; sampler passes are numbered separately."""
    if 'Loader' in class_type: return 'load'
    if class_type.startswith('TextGenerate'): return 'prompt_enhance'
    if 'TextEncode' in class_type: return 'text_encode'
    if class_type=='LTXVLatentUpsampler': return 'latent_upscale'
    if 'Decode' in class_type: return 'decode'
    if class_type.startswith(('Save','CreateVideo')): return 'export'
    return 'other'

def randomize_seeds(prompt):
    """Change every seed so ComfyUI cannot reuse cached sampler outputs from an earlier run."""
    for node in prompt.values():
        for key in ('noise_seed','seed'):
            if isinstance(node.get('inputs',{}).get(key),int): node['inputs'][key]=random.randrange(2**48)

async def run(base, prompt, client_id):
    """Queue the prompt and timestamp each node as ComfyUI reports it starting over the websocket."""
    import aiohttp
    events=[]; cached=[]; pid=None
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(base.replace('http','ws',1)+f'/ws?clientId={client_id}',max_msg_size=0) as ws:
            pid=request(base+'/prompt',{'prompt':prompt,'client_id':client_id})['prompt_id']
            async for msg in ws:
                if msg.type!=aiohttp.WSMsgType.TEXT: continue
                data=json.loads(msg.data); kind=data.get('type'); body=data.get('data',{})
                if body.get('prompt_id')!=pid: continue
                now=time.monotonic()
                if kind=='execution_cached': cached.extend(body.get('nodes',[]))
                elif kind=='executing':
                    events.append((now,body.get('node')))
                    if body.get('node') is None: break
                elif kind=='execution_interrupted': raise SystemExit('ComfyUI execution was interrupted.')
                elif kind=='execution_error': raise SystemExit(f"ComfyUI execution failed at node {body.get('node_id')}: {body.get('exception_message','').strip()}")
                elif kind=='execution_success':
                    events.append((now,None)); break
    return pid,events,cached

def summarize(prompt, events):
    nodes=[]; stages={}; sampler_pass=0
    for (start,node),(end,_) in zip(events,events[1:]):
        if node is None: continue
        class_type=prompt.get(str(node),{}).get('class_type','unknown')
        if class_type in ('SamplerCustomAdvanced','KSampler','KSamplerAdvanced'):
            sampler_pass+=1; stage=f'sample_pass_{sampler_pass}'
        else: stage=stage_of(class_type)
        seconds=round(end-start,2)
        nodes.append({'node':str(node),'class_type':class_type,'stage':stage,'seconds':seconds})
        stages[stage]=round(stages.get(stage,0)+seconds,2)
    return nodes,stages

def main():
    p=argparse.ArgumentParser(description='Measure one reproducible ComfyUI API workflow run, broken down by pipeline stage.')
    p.add_argument('--api',default='http://127.0.0.1:8188'); p.add_argument('--workflow',required=True,help='Workflow name / version label')
    p.add_argument('--resolution',required=True,help='WidthxHeight label, e.g. 960x544'); p.add_argument('--frames',type=int,required=True)
    p.add_argument('--prompt-json',required=True,help='ComfyUI API-format prompt JSON exported from the workflow')
    p.add_argument('--fresh',action='store_true',help='Randomize seeds so no sampler output is served from cache')
    p.add_argument('--cold',action='store_true',help='Unload models and free VRAM first so model loading is included')
    p.add_argument('--gpu-rate-usd-hour',type=float); p.add_argument('--output',default='/workspace/logs/benchmarks.jsonl')
    a=p.parse_args(); base=a.api.rstrip('/'); prompt=json.loads(Path(a.prompt_json).read_text())
    if 'prompt' in prompt and isinstance(prompt['prompt'],dict): prompt=prompt['prompt']
    if a.fresh: randomize_seeds(prompt)
    if a.cold: request(base+'/free',{'unload_models':True,'free_memory':True}); time.sleep(3)
    gpu,total,used=gpu_stats(); peaks=[used]; stop=threading.Event()
    def monitor():
        while not stop.wait(.5):
            try: peaks.append(gpu_stats()[2])
            except Exception: pass
    watcher=threading.Thread(target=monitor,daemon=True); watcher.start()
    start=time.monotonic()
    pid,events,cached=asyncio.run(run(base,prompt,str(uuid.uuid4())))
    elapsed=time.monotonic()-start; stop.set(); watcher.join(timeout=1)
    nodes,stages=summarize(prompt,events)
    attention=next((arg for arg in request(base+'/system_stats').get('system',{}).get('argv',[]) if 'attention' in arg),'default')
    result={'timestamp_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'gpu':gpu,'workflow':a.workflow,'resolution':a.resolution,'frames':a.frames,
            'attention':attention,'fresh':a.fresh,'cold':a.cold,'generation_seconds':round(elapsed,2),'stage_seconds':stages,'cached_nodes':len(cached),
            'peak_gpu_memory_mib':max(peaks),'frames_per_second':round(a.frames/elapsed,3),'prompt_id':pid,'nodes':nodes}
    if a.gpu_rate_usd_hour is not None: result['estimated_cost_usd']=round(elapsed/3600*a.gpu_rate_usd_hour,4)
    out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('a') as f: f.write(json.dumps(result)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='nodes'},indent=2))

if __name__=='__main__': main()
