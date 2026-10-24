# Workflow guide

For the selected `LTX_VERSION`, seven JSONs are read from `versions/<LTX_VERSION>/workflows/` and installed into `/workspace/ComfyUI/user/default/workflows/` only when the same filename is not already present. The selected profile's default graph is also installed as the initial frontend graph.

## Image to Video and Text to Video

The v9 filmmaker subgraph remains the base of Image to Video. It controls prompt text and rewrite, negative prompt, duration and frame construction, resolution, first-frame preprocessing, random seed, model/text encoder/VAEs, sampler and sigma schedule for each stage, video/audio CFG, latent upscaling, tiled decode, and MP4 output. Text to Video uses the official text-only LTX graph so there is no dormant image input.

The resolution selector presents aspect and megapixel controls. The default 0.5 MP landscape size is 960×544 when divisible by 32. Duration is converted using `1 + 8 * floor(seconds * fps / 8)`; at 30 seconds and 24 fps the result is 721 frames.

## First and Last Frame

This graph uses ComfyUI's official `video_ltx2_5_flf2v` workflow structure, which is single-stage. Replace `Opening Frame` and `Closing Frame` independently; the model generates the motion between them. Do not add a second-stage graph unless that path is validated for this template.

## Audio to Video

The official A2V graph trims the audio source, encodes and freezes audio reference tokens during denoising, then muxes the trimmed original audio waveform into the final MP4. The input audio is not decoded and regenerated as an output soundtrack. The duration should fit the supplied audio.

## Text to Audio

This official audio-only graph has an audio VAE, audio-only model wrapper, audio preview, and `SaveAudioAdvanced`. It does not load the video VAE or latent upscaler.

## Two Stage Advanced

The existing filmmaker two-stage graph exposes separate stage samplers, sigma schedules, guidance, and the latent spatial-upscale/refine path. The stage-one resolution is the base budget; the final image dimensions are approximately doubled by the spatial upscaler. Distilled guidance defaults to CFG 1.0; do not expect raising CFG to behave like an undistilled model.

## Ingredients

Ingredients is an IC-LoRA conditioning graph. Its reference sheet is resized and repeated into a guide video, injected with `LTXAddVideoICLoRAGuide`, and cropped out after sampling. This keeps the sheet from becoming the output's first frame. Its loader uses the dedicated Ingredients IC-LoRA at strength 1.0 and a compatible BF16 LTX-2.5 stack.

Prompt structure from the model card:

```text
Reference sheet: [describe each visible character, prop, wardrobe item, or location by its panel/position]

Generated video: [describe the action, framing, camera movement, and sound]
```

The model card's trained bucket is 768×448, 121 frames, 24 fps. Longer durations and other sizes are outside that training distribution. Keep the same reference-sheet file on the persistent `/workspace/ComfyUI/input/` volume and reuse it across shots; repeat the same visual identity details in each scene prompt.

## Inputs and output

Workflows do not depend on sample image/audio files. Upload your own assets into the labeled Load nodes. Outputs are MP4 or audio under `/workspace/ComfyUI/output/`; temporary files and model weights are outside the output tree.
