#!/usr/bin/env python3
"""Time video decoding alone for several decoder settings on a running ComfyUI.

Decodes an empty latent with the stage-2 output shape, so no sampling runs and each
preset takes only as long as its decode. Uses the standard library only and reads
timings from ComfyUI's job history, so it can target a Pod's proxy URL from anywhere.

Presets:
  core:TILE/OVERLAP/TEMPORAL/TEMPORAL_OVERLAP           core VAEDecodeTiled, pixel units
  ltxv:TILES/OVERLAP/TEMPORAL/TEMPORAL_OVERLAP/DTYPE    LTXVSpatioTemporalTiledVAEDecode, latent units
"""
import argparse, json, time, urllib.request, uuid
from pathlib import Path

# The packaged default first, then Lightricks' high-VRAM tile setting, then the LTXV decoder.
PRESETS = 'core:512/64/64/16,core:1024/256/128/48,ltxv:4/1/16/1/auto,ltxv:2/1/16/1/auto,ltxv:2/1/16/1/float16'


def call(base, path, body=None):
    req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json', 'User-Agent': 'ltx-benchmark'})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
        return json.loads(raw) if raw.strip() else {}


def decoder_node(preset):
    kind, _, values = preset.partition(':')
    parts = values.split('/')
    if kind == 'core':
        tile, overlap, temporal, temporal_overlap = (int(v) for v in parts)
        return {'class_type': 'VAEDecodeTiled', 'inputs': {'samples': ['2', 0], 'vae': ['1', 0], 'tile_size': tile, 'overlap': overlap,
                                                           'temporal_size': temporal, 'temporal_overlap': temporal_overlap}}
    if kind == 'ltxv':
        tiles, overlap, temporal, temporal_overlap = (int(v) for v in parts[:4])
        return {'class_type': 'LTXVSpatioTemporalTiledVAEDecode', 'inputs': {
            'vae': ['1', 0], 'latents': ['2', 0], 'spatial_tiles': tiles, 'spatial_overlap': overlap, 'temporal_tile_length': temporal,
            'temporal_overlap': temporal_overlap, 'last_frame_fix': False, 'working_device': 'auto', 'working_dtype': parts[4] if len(parts) > 4 else 'auto'}}
    raise SystemExit(f'Unknown preset {preset!r}; use core:... or ltxv:...')


def prompt_for(vae, width, height, frames, preset):
    return {
        '1': {'class_type': 'VAELoader', 'inputs': {'vae_name': vae}},
        '2': {'class_type': 'EmptyLTXVLatentVideo', 'inputs': {'width': width, 'height': height, 'length': frames, 'batch_size': 1}},
        '3': decoder_node(preset),
        '4': {'class_type': 'ImageFromBatch', 'inputs': {'image': ['3', 0], 'batch_index': 0, 'length': 1}},
        '5': {'class_type': 'PreviewImage', 'inputs': {'images': ['4', 0]}},
    }


def run(base, prompt):
    """Queue a prompt, wait for it, and return (seconds, error) from ComfyUI's own start/finish timestamps."""
    pid = call(base, '/prompt', {'prompt': prompt, 'client_id': str(uuid.uuid4())})['prompt_id']
    while True:
        time.sleep(3)
        entry = call(base, f'/history/{pid}').get(pid)
        if entry and entry.get('status', {}).get('completed') is not None and entry['status'].get('status_str') in ('success', 'error'):
            break
    messages = {name: data for name, data in entry['status'].get('messages', [])}
    end = messages.get('execution_success') or messages.get('execution_error') or {}
    seconds = (end.get('timestamp', 0) - messages['execution_start']['timestamp']) / 1000
    error = messages.get('execution_error', {}).get('exception_message')
    return round(seconds, 1), (error or '').strip()[:300] or None


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--api', default='http://127.0.0.1:8188')
    p.add_argument('--vae', default='ltx-2.5-video-vae-conv-bf16.safetensors')
    p.add_argument('--width', type=int, default=1920, help='Decoded width (stage 2 output: twice the stage-1 width)')
    p.add_argument('--height', type=int, default=1088)
    p.add_argument('--frames', type=int, default=721)
    p.add_argument('--presets', default=PRESETS, help='Comma-separated presets (see the description)')
    p.add_argument('--output', default='/workspace/logs/decode-benchmarks.jsonl')
    a = p.parse_args(); base = a.api.rstrip('/')
    gpu = call(base, '/system_stats')['devices'][0]['name']
    print(f'[decode] {gpu}; {a.vae}; {a.width}x{a.height}x{a.frames}. Jobs queue behind any pending ComfyUI work.', flush=True)
    # Warm up so the VAE load is not charged to the first preset.
    run(base, prompt_for(a.vae, 256, 256, 9, 'core:256/64/64/16'))
    rows = []
    for preset in (x.strip() for x in a.presets.split(',')):
        seconds, error = run(base, prompt_for(a.vae, a.width, a.height, a.frames, preset))
        row = {'preset': preset, 'seconds': seconds} if not error else {'preset': preset, 'error': error}
        print(f"[decode] {preset:>24}: " + (f'{seconds:.1f}s' if not error else f'ERROR {error}'), flush=True)
        rows.append(row)
    result = {'timestamp_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'gpu': gpu, 'vae': a.vae,
              'shape': f'{a.width}x{a.height}x{a.frames}', 'results': rows}
    try:
        out = Path(a.output); out.parent.mkdir(parents=True, exist_ok=True)
        with out.open('a') as f: f.write(json.dumps(result) + '\n')
    except OSError:
        pass
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
