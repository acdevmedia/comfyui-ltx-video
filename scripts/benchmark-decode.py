#!/usr/bin/env python3
"""Time VAEDecodeTiled alone for several tile presets on a running ComfyUI.

Decodes an empty latent with the stage-2 output shape, so no sampling runs and each
preset takes only as long as its decode. Runs remotely too (no nvidia-smi needed).
"""
import argparse, asyncio, json, sys, time, uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark import request, run, summarize  # noqa: E402

# Pixel settings tile/overlap/temporal/temporal_overlap; the first is the packaged default,
# the rest come from the Decode notes in Lightricks' LTX-2.5 reference graphs.
PRESETS = '512/64/64/16,512/64/128/32,768/192/128/32,1024/256/128/48,1536/384/192/48'

def prompt_for(vae, width, height, frames, tile):
    tile_size, overlap, temporal_size, temporal_overlap = tile
    return {
        '1': {'class_type': 'VAELoader', 'inputs': {'vae_name': vae}},
        '2': {'class_type': 'EmptyLTXVLatentVideo', 'inputs': {'width': width, 'height': height, 'length': frames, 'batch_size': 1}},
        '3': {'class_type': 'VAEDecodeTiled', 'inputs': {'samples': ['2', 0], 'vae': ['1', 0], 'tile_size': tile_size, 'overlap': overlap,
                                                        'temporal_size': temporal_size, 'temporal_overlap': temporal_overlap}},
        '4': {'class_type': 'ImageFromBatch', 'inputs': {'image': ['3', 0], 'batch_index': 0, 'length': 1}},
        '5': {'class_type': 'PreviewImage', 'inputs': {'images': ['4', 0]}},
    }

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--api', default='http://127.0.0.1:8188')
    p.add_argument('--vae', default='ltx-2.5-video-vae-conv-bf16.safetensors')
    p.add_argument('--width', type=int, default=1920, help='Decoded width (stage 2 output: twice the stage-1 width)')
    p.add_argument('--height', type=int, default=1088)
    p.add_argument('--frames', type=int, default=721)
    p.add_argument('--presets', default=PRESETS, help='Comma-separated tile/overlap/temporal/temporal_overlap pixel settings')
    p.add_argument('--output', default='/workspace/logs/decode-benchmarks.jsonl')
    a = p.parse_args(); base = a.api.rstrip('/')
    stats = request(base + '/system_stats'); gpu = stats['devices'][0]['name']
    print(f'[decode] {gpu}; {a.vae}; {a.width}x{a.height}x{a.frames}. Jobs queue behind any pending ComfyUI work.', flush=True)
    # Warm up so the VAE load and kernel setup are not charged to the first preset.
    asyncio.run(run(base, prompt_for(a.vae, 256, 256, 9, (256, 64, 64, 16)), str(uuid.uuid4())))
    rows = []
    for preset in a.presets.split(','):
        tile = tuple(int(v) for v in preset.strip().split('/'))
        prompt = prompt_for(a.vae, a.width, a.height, a.frames, tile)
        try:
            _, events, _ = asyncio.run(run(base, prompt, str(uuid.uuid4())))
            seconds = next((n['seconds'] for n in summarize(prompt, events)[0] if n['class_type'] == 'VAEDecodeTiled'), None)
            row = {'preset': preset.strip(), 'decode_seconds': seconds}
        except SystemExit as exc:
            row = {'preset': preset.strip(), 'error': str(exc)[:300]}
        print(f"[decode] {row['preset']:>18}: " + (f"{row['decode_seconds']:.1f}s" if 'decode_seconds' in row and row['decode_seconds'] is not None else row.get('error', 'no timing')), flush=True)
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
