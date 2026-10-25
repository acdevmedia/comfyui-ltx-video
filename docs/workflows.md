# Workflow guide

For the selected `LTX_VERSION`, ten JSONs are read from `versions/<LTX_VERSION>/workflows/` and installed into `/workspace/ComfyUI/user/default/workflows/` only when the same filename is not already present. The selected profile's default graph is also installed as the initial frontend graph.

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

## Negative prompts and CFG

Image to Video, Text to Video, First and Last Frame, and Two Stage Advanced expose a negative prompt on their control panel, wired to the negative `CLIPTextEncode` inside the subgraph. The distilled defaults use `LTXVDualCFGGuider` with video and audio CFG both at 1.0. At equal scales of 1.0 ComfyUI skips the negative (unconditional) pass entirely, so the negative prompt has no effect until a CFG value is raised above 1.0. Raising CFG adds a second model evaluation to every sampling step, roughly doubling sampling time, and the distilled model is not tuned for higher guidance; test on short clips before relying on it.

## Extend Video (After and Before)

Workflows 08 and 09 take an uploaded clip and return one MP4 containing the clip plus a newly generated section, with sound. Everything is assembled inside ComfyUI; no external FFmpeg step is needed.

- **Real context, not a single frame.** The last (or first) 9, 17, 25... frames of the clip are pinned into the new generation with core `LTXVAddGuide` (frame index 0 for After, the end of the new section for Before). The generated copies of those frames are then dropped and the original frames kept, so the join is the clip's own pixels. On a 6-second 1280x704 test the frames either side of the join matched exactly in both directions.
- **Sound.** The new section's audio is generated jointly with the picture. Five seconds of the clip's own sound are attached as a voice reference (`LTXVSetAudioRefTokens`), so the same voices carry on. The clip's original sound is kept unchanged and joined with `AudioConcat`; clips without sound fall back to silence.
- **Resolution.** The clip is resized and centre-cropped to the working Width x Height (default 1280x704) and generated in a single distilled pass, so the whole output is at that size. A 3-second extension of the test clip took about 90-100 s on an A100.
- `LTXVExtendSampler` from ComfyUI-LTXVideo was not used: it predates LTX-2's joint audio-video latents and only handles video.

## New Angle

Workflow 10 is for shooting coverage, such as over-the-shoulder reverses, that cut against an existing clip on the same audio track. The clip's sound for the chosen section is encoded and frozen (`frozen_audio` from `LTXVSetAudioRefTokens`, a zero noise mask), the picture is generated to fit it, and the untouched original waveform is muxed into the result.

There is no LTX-2.5 adapter that moves the camera on existing footage; the official IC-LoRA catalogue has no novel-view or re-camera model, and Layout to Render explicitly keeps the source camera. New Angle therefore re-stages the moment: the camera position comes from the prompt, and the cast and set come from a **reference sheet** through the Ingredients IC-LoRA.

GPU testing showed that the sheet must be a real reference sheet, as the Ingredients model card describes: clean panels for each person, prop and location on a plain background. A still taken from the clip, a grid of stills, or face crops cut from the frame are all reproduced as layout, so the output copies the original framing even at reduced guide strength. With a proper sheet the model composes a new shot. Without any sheet the prompt alone produces a genuine over-the-shoulder angle, but with different people and a different room. The workflow therefore takes the sheet as an upload; make it from stills of the clip with an image tool.

Limits: five seconds (121 frames at 24 fps, 768x448) is the trained bucket; the performance is newly generated rather than copied from the clip; and it needs the BF16 Ingredients stack (`AUTO_DOWNLOAD_ADAPTERS=true`).

## Regenerating 08-10

`scripts/v2v_graphs.py` defines these three graphs in ComfyUI API format and can print a prompt for direct testing. The editable UI files in `archive/v2v-workflow-sources/` were produced from those definitions by the installed ComfyUI frontend (`app.loadApiJson`, then grouped and serialized), and each was checked to convert back to exactly the tested prompt. After changing a graph, repeat that conversion on a running Pod and re-run `scripts/package-workflows.py`.

