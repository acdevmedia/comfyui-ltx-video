#!/usr/bin/env python3
"""Video-in, video-out LTX-2.5 graphs in ComfyUI API format.

Each builder returns (prompt, layout): the API prompt ComfyUI executes, and a layout hint
(node id -> group) used when the graph is converted into an editable UI workflow.

  python3 scripts/v2v_graphs.py extend_after --video clip.mp4 > prompt.json
"""
import argparse, json, sys

DISTILLED_SIGMAS = '1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0'
INT8_TRANSFORMER = 'ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors'
INT8_TEXT_ENCODER = 'gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors'
BF16_TRANSFORMER = 'ltx-2.5-22b-distilled-transformer-bf16.safetensors'
BF16_TEXT_ENCODER = 'gemma4-12b-with-proj-ltx-2.5-bf16.safetensors'
INGREDIENTS_LORA = 'ltx-2.5-22b-ic-lora-ingredients-0.9.safetensors'
CONV_VIDEO_VAE = 'ltx-2.5-video-vae-conv-bf16.safetensors'
QUALITY_VIDEO_VAE = 'ltx-2.5-video-vae-bf16.safetensors'
AUDIO_VAE = 'ltx-2.5-audio-vae-bf16.safetensors'
NEGATIVE = ('blurry, out of focus, oversharpened, waxy skin, deformed faces, incorrect hands, extra fingers, duplicate limbs, '
            'identity drift, changing clothing, flicker, frame jitter, unwanted cuts, exposure pumping, inconsistent lighting, '
            'color shifts, CGI appearance, distorted voices, robotic speech, watermarks')

GROUPS = ('Your Clip & Controls', 'Timing', 'Models', 'Prompt & Sound', 'Generate', 'Assemble & Save')


class Graph:
    def __init__(self):
        self.prompt, self.layout = {}, {}

    def add(self, class_type, group, title=None, **inputs):
        node_id = str(len(self.prompt) + 1)
        api_inputs = {}
        for name, value in inputs.items():
            # Autogrow sockets such as values.a / images.image0 are written with a double underscore.
            api_inputs[name.replace('__', '.')] = list(value) if isinstance(value, tuple) else value
        self.prompt[node_id] = {'class_type': class_type, 'inputs': api_inputs, '_meta': {'title': title or class_type}}
        self.layout[node_id] = group
        return Ref(node_id)

    def math(self, expression, title, group='Timing', **values):
        return self.add('ComfyMathExpression', group, title, expression=expression, **{f'values__{k}': v for k, v in values.items()})


class Ref(str):
    def __getitem__(self, slot):
        return (str(self), slot)


def _common(g, video_file, width, height, fit_clip=True):
    c = 'Your Clip & Controls'
    video = g.add('LoadVideo', c, 'Your Clip', file=video_file)
    parts = g.add('GetVideoComponents', c, 'Split Clip into Frames, Sound and FPS', video=video[0])
    w = g.add('PrimitiveInt', c, 'Width (multiple of 32)', value=width)
    h = g.add('PrimitiveInt', c, 'Height (multiple of 32)', value=height)
    frames = g.add('ImageScale', c, 'Fit Clip to Working Size', image=parts[0], upscale_method='lanczos', width=w[0], height=h[0], crop='center') if fit_clip else None
    count = g.add('GetImageSize', 'Timing', 'Count Clip Frames', image=parts[0])
    seconds = g.math('a / b', 'Clip Length (seconds)', a=count[2], b=parts[2])
    silence = g.add('EmptyAudio', 'Prompt & Sound', 'Silence (if the clip has no sound)', duration=seconds[0], sample_rate=44100, channels=2)
    sound = g.add('AudioMerge', 'Prompt & Sound', 'Clip Sound (or silence)', audio1=parts[1], audio2=silence[0], merge_method='add')
    return parts, w, h, frames, sound


def _sampler(g, model, positive, negative, latent, seed):
    s = 'Generate'
    noise = g.add('RandomNoise', s, 'Noise', noise_seed=seed[0])
    sampler = g.add('KSamplerSelect', s, 'Sampler', sampler_name='euler_ancestral')
    sigmas = g.add('ManualSigmas', s, 'Distilled 8-Step Schedule', sigmas=DISTILLED_SIGMAS)
    guider = g.add('CFGGuider', s, 'Guidance (CFG 1.0 for distilled)', model=model, positive=positive, negative=negative, cfg=1.0)
    out = g.add('SamplerCustomAdvanced', s, 'Generate', noise=noise[0], guider=guider[0], sampler=sampler[0], sigmas=sigmas[0], latent_image=latent)
    return g.add('LTXVSeparateAVLatent', s, 'Split Picture and Sound', av_latent=out[0])


def extend(direction, video_file='', prompt=None, seconds=5.0, context_frames=25, width=1280, height=704, seed=42):
    """Continue a clip forwards ('after') or lead into it ('before'), conditioned on real frames from the clip."""
    assert direction in ('after', 'before')
    g = Graph(); c = 'Your Clip & Controls'
    parts, w, h, frames, sound = _common(g, video_file, width, height)
    default_prompt = (
        'Continue the shot naturally. [Describe what happens next: action, dialogue, camera.] Keep the same people, wardrobe, '
        'location, lighting and lens.' if direction == 'after' else
        '[Describe what happens just before the clip starts.] It leads straight into the opening of the original shot. Keep the '
        'same people, wardrobe, location, lighting and lens.')
    text = g.add('PrimitiveStringMultiline', c, 'What Happens Next' if direction == 'after' else 'What Happens Before', value=prompt or default_prompt)
    negative = g.add('PrimitiveStringMultiline', c, 'Negative Prompt (CFG 1.0: little/no effect)', value=NEGATIVE)
    extra = g.add('PrimitiveFloat', c, 'Seconds to Add', value=seconds)
    context = g.add('PrimitiveInt', c, 'Frames of Your Clip to Match (9, 17, 25, 33...)', value=context_frames)
    seed_node = g.add('PrimitiveInt', c, 'Seed', value=seed)

    n_context = g.math('max(9, 1 + floor((a - 1) / 8) * 8)', 'Context Frames (8n+1)', a=context[0])
    n_new = g.math('max(8, floor(a * b / 8) * 8)', 'New Frames (multiple of 8)', a=extra[0], b=parts[2])
    n_total = g.math('a + b', 'Frames to Generate', a=n_context[1], b=n_new[1])
    if direction == 'after':
        context_frames_node = g.add('ImageFromBatch', 'Timing', 'Last Frames of Your Clip', image=frames[0],
                                    batch_index=g.math('-a', 'From the End', a=n_context[1])[1], length=n_context[1])
        guide_index, voice_start = 0, -5.0
    else:
        context_frames_node = g.add('ImageFromBatch', 'Timing', 'First Frames of Your Clip', image=frames[0], batch_index=0, length=n_context[1])
        guide_index, voice_start = n_new[1], 0.0

    m = 'Models'
    model = g.add('UNETLoader', m, 'LTX-2.5 Distilled (INT8)', unet_name=INT8_TRANSFORMER, weight_dtype='default')
    clip = g.add('CLIPLoader', m, 'Text Encoder (INT8)', clip_name=INT8_TEXT_ENCODER, type='ltxv', device='default')
    vae = g.add('VAELoader', m, 'Video Decoder (conv)', vae_name=CONV_VIDEO_VAE)
    audio_vae = g.add('VAELoader', m, 'Audio VAE', vae_name=AUDIO_VAE)

    p = 'Prompt & Sound'
    pos = g.add('CLIPTextEncode', p, 'Encode Prompt', text=text[0], clip=clip[0])
    neg = g.add('CLIPTextEncode', p, 'Encode Negative Prompt', text=negative[0], clip=clip[0])
    cond = g.add('LTXVConditioning', p, 'Match Clip Frame Rate', positive=pos[0], negative=neg[0], frame_rate=parts[2])
    # Five seconds of the clip's own sound give the new section's generated audio the same voices.
    voice = g.add('TrimAudioDuration', p, 'Voice Reference (5 s of your clip)', audio=sound[0], start_index=voice_start, duration=5.0)
    voice_latent = g.add('VAEEncodeAudio', p, 'Encode Voice Reference', audio=voice[0], vae=audio_vae[0])
    voiced = g.add('LTXVSetAudioRefTokens', p, 'Keep the Same Voices', positive=cond[0], negative=cond[1], audio_latent=voice_latent[0])

    s = 'Generate'
    empty = g.add('EmptyLTXVLatentVideo', s, 'Empty Video', width=w[0], height=h[0], length=n_total[1], batch_size=1)
    guided = g.add('LTXVAddGuide', s, 'Pin Your Clip\'s Frames in Place', positive=voiced[0], negative=voiced[1], vae=vae[0],
                   latent=empty[0], image=context_frames_node[0], frame_idx=guide_index, strength=1.0)
    empty_audio = g.add('LTXVEmptyLatentAudio', s, 'Empty Sound', frames_number=n_total[1], frame_rate=parts[2], batch_size=1, audio_vae=audio_vae[0])
    av = g.add('LTXVConcatAVLatent', s, 'Join Picture and Sound', video_latent=guided[2], audio_latent=empty_audio[0])
    sep = _sampler(g, model[0], guided[0], guided[1], av[0], seed_node)
    cropped = g.add('LTXVCropGuides', s, 'Remove Guide Frames', positive=guided[0], negative=guided[1], latent=sep[0])

    a = 'Assemble & Save'
    decoded = g.add('VAEDecodeTiled', a, 'Decode Picture', samples=cropped[2], vae=vae[0], tile_size=512, overlap=64, temporal_size=64, temporal_overlap=16)
    new_audio = g.add('LTXVAudioVAEDecode', a, 'Decode Sound', samples=sep[1], audio_vae=audio_vae[0])
    new_seconds = g.math('a / b', 'New Section Length (s)', group=a, a=n_new[1], b=parts[2])
    if direction == 'after':
        new_frames = g.add('ImageFromBatch', a, 'New Frames Only', image=decoded[0], batch_index=n_context[1], length=n_new[1])
        skip = g.math('a / b', 'Matched Section Length (s)', group=a, a=n_context[1], b=parts[2])
        new_sound = g.add('TrimAudioDuration', a, 'New Sound Only', audio=new_audio[0], start_index=skip[0], duration=new_seconds[0])
        joined = g.add('BatchImagesNode', a, 'Your Clip + New Frames', images__image0=frames[0], images__image1=new_frames[0])
    else:
        new_frames = g.add('ImageFromBatch', a, 'New Frames Only', image=decoded[0], batch_index=0, length=n_new[1])
        new_sound = g.add('TrimAudioDuration', a, 'New Sound Only', audio=new_audio[0], start_index=0.0, duration=new_seconds[0])
        joined = g.add('BatchImagesNode', a, 'New Frames + Your Clip', images__image0=new_frames[0], images__image1=frames[0])
    all_sound = g.add('AudioConcat', a, 'Join Sound', audio1=sound[0], audio2=new_sound[0], direction=direction)
    video = g.add('CreateVideo', a, 'Build Video', images=joined[0], fps=parts[2], audio=all_sound[0], bit_depth='auto', color_space='sRGB', codec='none')
    g.add('SaveVideo', a, 'Save Extended Video', video=video[0], filename_prefix=f'video/LTX25_extend_{direction}', format='auto', format__codec='auto', codec='auto')
    return g.prompt, g.layout


def new_angle(video_file='', sheet_file='', prompt=None, start=0.0, seconds=5.0, width=768, height=448, seed=42):
    """Re-shoot a moment of the clip from a new camera position, locked to the clip's original sound.

    The Ingredients IC-LoRA needs a real reference sheet (clean panels on a plain background). Stills cut
    from the clip itself are reproduced as layout rather than used as reference, so the sheet is an input.
    """
    g = Graph(); c = 'Your Clip & Controls'
    parts, w, h, _, sound = _common(g, video_file, width, height, fit_clip=False)
    sheet_image = g.add('LoadImage', c, 'Reference Sheet (cast, props, location)', image=sheet_file)
    default_prompt = (
        'Reference sheet: Top Left (Character): [name and describe the first person]. Top Right (Character): [the second person]. '
        'Bottom (Setting): [the location].\n\n'
        'Generated video: [new camera position], for example an over-the-shoulder shot from behind [person A], their shoulder soft in '
        'the foreground, looking at [person B] as they speak. Same place, same lighting, same moment. [Camera movement, e.g. locked off.]')
    text = g.add('PrimitiveStringMultiline', c, 'Describe the Sheet and the New Angle', value=prompt or default_prompt)
    negative = g.add('PrimitiveStringMultiline', c, 'Negative Prompt (CFG 1.0: little/no effect)', value=NEGATIVE)
    start_node = g.add('PrimitiveFloat', c, 'Start Time in Your Clip (s)', value=start)
    length_node = g.add('PrimitiveFloat', c, 'Shot Length (s, 5 recommended)', value=seconds)
    seed_node = g.add('PrimitiveInt', c, 'Seed', value=seed)

    t = 'Timing'
    n_frames = g.math('1 + floor(a * b / 8) * 8', 'Frames to Generate (8n+1)', a=length_node[0], b=parts[2])
    shot_seconds = g.math('a / b', 'Exact Shot Length (s)', a=n_frames[1], b=parts[2])
    sheet = g.add('ImageScale', t, 'Fit Sheet to Working Size', image=sheet_image[0], upscale_method='lanczos', width=w[0], height=h[0], crop='disabled')
    guide = g.add('RepeatImageBatch', t, 'Hold Sheet for the Whole Shot', image=sheet[0], amount=n_frames[1])

    m = 'Models'
    model = g.add('UNETLoader', m, 'LTX-2.5 Distilled (BF16, for Ingredients)', unet_name=BF16_TRANSFORMER, weight_dtype='default')
    lora = g.add('LTXICLoRALoaderModelOnly', m, 'Ingredients IC-LoRA (keeps cast & set)', model=model[0], lora_name=INGREDIENTS_LORA, strength_model=1.0)
    clip = g.add('CLIPLoader', m, 'Text Encoder (BF16)', clip_name=BF16_TEXT_ENCODER, type='ltxv', device='default')
    vae = g.add('VAELoader', m, 'Video Decoder (best quality)', vae_name=QUALITY_VIDEO_VAE)
    audio_vae = g.add('VAELoader', m, 'Audio VAE', vae_name=AUDIO_VAE)

    p = 'Prompt & Sound'
    pos = g.add('CLIPTextEncode', p, 'Encode Prompt', text=text[0], clip=clip[0])
    neg = g.add('CLIPTextEncode', p, 'Encode Negative Prompt', text=negative[0], clip=clip[0])
    cond = g.add('LTXVConditioning', p, 'Match Clip Frame Rate', positive=pos[0], negative=neg[0], frame_rate=parts[2])
    shot_sound = g.add('TrimAudioDuration', p, 'Original Sound for This Shot', audio=sound[0], start_index=start_node[0], duration=shot_seconds[0])
    sound_latent = g.add('VAEEncodeAudio', p, 'Encode Original Sound', audio=shot_sound[0], vae=audio_vae[0])
    # frozen_audio has a zero noise mask: the soundtrack is held exactly while the picture is generated to fit it.
    frozen = g.add('LTXVSetAudioRefTokens', p, 'Lock the Original Sound', positive=cond[0], negative=cond[1], audio_latent=sound_latent[0])

    s = 'Generate'
    empty = g.add('EmptyLTXVLatentVideo', s, 'Empty Video', width=w[0], height=h[0], length=n_frames[1], batch_size=1)
    guided = g.add('LTXAddVideoICLoRAGuide', s, 'Show the Model Your Reference Sheet', positive=cond[0], negative=cond[1], vae=vae[0], latent=empty[0],
                   image=guide[0], frame_idx=0, strength=1.0, latent_downscale_factor=lora[1], crop='disabled', use_tiled_encode=False,
                   tile_size=256, tile_overlap=64, use_streaming=False, tile_frames=97)
    av = g.add('LTXVConcatAVLatent', s, 'Join Picture and Locked Sound', video_latent=guided[2], audio_latent=frozen[2])
    sep = _sampler(g, lora[0], guided[0], guided[1], av[0], seed_node)
    cropped = g.add('LTXVCropGuides', s, 'Remove Reference Frames', positive=guided[0], negative=guided[1], latent=sep[0])

    a = 'Assemble & Save'
    decoded = g.add('VAEDecodeTiled', a, 'Decode Picture', samples=cropped[2], vae=vae[0], tile_size=512, overlap=64, temporal_size=64, temporal_overlap=16)
    # Mux the untouched original waveform so the new angle lines up sample-for-sample in the edit.
    video = g.add('CreateVideo', a, 'Build Video with Original Sound', images=decoded[0], fps=parts[2], audio=shot_sound[0], bit_depth='auto', color_space='sRGB', codec='none')
    g.add('SaveVideo', a, 'Save New Angle', video=video[0], filename_prefix='video/LTX25_new_angle', format='auto', format__codec='auto', codec='auto')
    return g.prompt, g.layout


BUILDERS = {
    'extend_after': lambda **kw: extend('after', **kw),
    'extend_before': lambda **kw: extend('before', **kw),
    'new_angle': new_angle,
}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('graph', choices=sorted(BUILDERS))
    p.add_argument('--video', default='', help='File name in ComfyUI/input')
    p.add_argument('--sheet', default='', help='Reference sheet image in ComfyUI/input (new_angle only)')
    p.add_argument('--set', action='append', default=[], metavar='KEY=VALUE', help='Override a builder default, e.g. seconds=2')
    p.add_argument('--layout', action='store_true', help='Emit {"prompt", "layout"} instead of the bare prompt')
    a = p.parse_args()
    overrides = {}
    for item in a.set:
        key, value = item.split('=', 1)
        try:
            overrides[key] = json.loads(value)
        except ValueError:
            overrides[key] = value
    if a.sheet: overrides['sheet_file'] = a.sheet
    prompt, layout = BUILDERS[a.graph](video_file=a.video, **overrides)
    json.dump({'prompt': prompt, 'layout': layout} if a.layout else prompt, sys.stdout, indent=1)


if __name__ == '__main__':
    main()
