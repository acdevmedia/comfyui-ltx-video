# LTX-2.5 prompt collection (revised)

12 reference prompts, rewritten against the official LTX prompting guide for LTX-2.5. 01–05 are grounded, realistic scenes; 06–12 are cinematic stress tests. Each file follows one of three templates below.

| # | File | Template |
|---|------|----------|
| 01 | detective_tracking | B – single shot, dialogue |
| 02 | country_house_confrontation | C – multi-shot (3 shots), dialogue |
| 03 | factory_floor | B – single shot, dialogue |
| 04 | railway_platform | A – single shot, no dialogue |
| 05 | awkward_dinner_party | C – multi-shot (3 shots), dialogue |
| 06 | romantic_kiss | A – single shot, no dialogue |
| 07 | helicopter_car_chase | C – multi-shot (4 shots) |
| 08 | ufo_stealth_bomber | C – multi-shot (3 shots) |
| 09 | alien_space_fleet | C – multi-shot (3 shots) |
| 10 | alien_first_contact | B – single shot, dialogue |
| 11 | dragon_attack | C – multi-shot (3 shots) |
| 12 | spaceship_crash | C – multi-shot (3 shots) |

---

## Template A – single shot, no dialogue

One flowing paragraph, present tense, no heading.

1. Shot type and camera at the start, then location and time of day.
2. The lighting sentence (see "Writing the lighting" below).
3. Who is in frame: age, hair, clothes, one or two distinguishing details, where they sit in the frame, and how the light falls on their face.
4. The action, one physical verb per sentence (looks, slips, turns, steps). Write pauses in as beats ("she waits", "a beat of silence").
5. What the camera does and where it ends up, and how the subject looks once it gets there.
6. Sound, in the order it happens.
7. Close with `No music.`

## Template B – single shot with dialogue (screenplay style)

```
INT./EXT. PLACE – TIME

[Shot and camera]. [Setting]. [Lighting sentence]. [Character: age, hair, clothes, what they hold, light on the face].

[Action]. [Speaker] [physical cue] and says in a [voice quality] [accent], "Short line." [Physical cue or "A beat."] "Next short line." ...

[Where the camera ends and what the final frame shows].

[Audio: voice quality, room sound, effects]. No music.
```

- Name the accent and voice quality the first time each person speaks.
- Break long lines into short pieces with a physical cue or a pause between them.
- Tie every line to a named speaker so the model knows whose lips move.

## Template C – multi-shot

One chronological paragraph. No heading, no shot list. Two to four shots.

```
[Shot 1: scale, camera, setting, lighting sentence, characters with fixed identifiers, action, sound].
A hard cut transitions to [scale + angle] of [same subject, same identifiers: "the silver-haired woman in the dark blue dress"], [her face lit by the same soft window light from the left]; [what sound carries across the cut]. [Action / dialogue].
A hard cut transitions to ... [same pattern].
[Final frame]. [Sound summary]. No music.
```

At every cut: name the cut, give the new framing, re-identify the subject with the same words used before, restate the light on them, and say what the sound does.

---

## Writing the lighting

Lighting is written into each prompt, not added as a shared block. The guide asks for one light logic per shot, and a single block cannot fit a lamplit room at night, deep space and a sunlit street at once.

One or two sentences, right after the setting, covering:

1. **Source and direction** – "soft overcast daylight from tall windows on his left", "a warm, fabric-shaded ceiling lamp above the table", "a distant white star on the right".
2. **Quality** – soft, even, diffused, bright; for hard sun, say where the shadows fall.
3. **Faces** – "lights his face clearly, with gentle shadows on his right side, natural skin tones".
4. **Shadows** – say there is detail in them ("open detail in the darker corners", "readable darkness").
5. **Colour** – two or three named colours plus neutral or true whites.

For a second light source, give it a job that does not compete with the first (sun on top, cloud bounce underneath; skylight from above, glowing plants from below). In multi-shot prompts, restate the light in a short phrase after each cut.

---

## Rules applied to all 12

- Emotions shown as physical cues ("her lips pressed together", "his jaw sets"), never as labels ("uncertain", "apprehensive").
- No measurements. "About the size of an airliner" instead of "approximately sixty metres"; "an arm's length apart" instead of "a metre".
- No instructions aimed at the model ("anatomy remains consistent", "no sudden changes in appearance", "physically convincing"). The model can't act on them; they only use up tokens.
- Long negative lists in the prompt replaced by a short `No music.` at the end, the same way the official frog example does it.
- Every beat the clip needs is written in. The duration predictor will not add pauses on its own.

---

## Settings notes

**Negative prompt.** `negative_prompt_comfyui.txt` is the full string to paste into ComfyUI: the template's own default (`pc game, console game, video game, cartoon, childish, ugly`), then the lighting list, then the audio list. The two `_append` files are the same lists kept separately.

The official distilled template runs at CFG 1 for video and audio, and at CFG 1 the negative prompt has no effect. To let it count, raise CFG slightly; LTX's Two-Stage Generation guide says raising CFG does not help the distilled model the way it helps a standard one, and to stay within 1.0–1.5 if you experiment. Compare against a CFG 1 run on the same seed to see whether it is helping.

The negative applies to every scene at once, so it only lists things none of the 12 scenes want. Terms that would fight a scene were removed: see the table below.

| Removed | Scene it would fight |
|---|---|
| harsh direct sunlight, hard directional lighting, harsh shadows (kept as "harsh shadows on faces") | 07 street sun, 12 desert sun |
| artificial glow, neon colour casts | 10 glowing plants, 09 engine glow |
| flickering illumination | 11 firelight |
| crushed blacks | 09 black space |
| excessive backlighting | 08, 11 silhouettes against the sky (kept "silhouetted faces") |
| dull grey exposure | 01, 02, 04 overcast daylight |
| humming, buzzing | 01 office lights, 03 ventilation, 08 disc hum, 10 alien breathing |
| crackling | 11 burning timber |
| echo, unwanted reverb | 11 roar echoing off walls, 03 factory acoustics |
| muffled speech, metallic voices | 10 helmet-filtered voice |
| excessive background noise | 03 factory floor |
| abrupt audio cuts | multi-shot prompts cut on purpose |

If you add new scenes, check them against this list the same way.

**Audio positive block.** Not added. Every prompt already names its sounds, says the voices are clear, and ends with `No music.` The rest of that block was instructions to the model ("correctly paced and synchronised") and things to avoid, which belong in the negative.

**30 seconds is beyond what LTX-2.5 currently offers on the API.** `ltx-2-5-fast` tops out at 20 seconds (720p/1080p at 24 or 25 fps); `ltx-2-5-pro` at 10 seconds. These prompts are paced to land in the 10–20 second range. Either send `"duration": null` and let the model size the clip to the action, or set a fixed length. Locally, frame counts must be 1 + a multiple of 8 (e.g. 481 frames ≈ 20 s at 24 fps); check your VRAM before going long.

**Prompt enhancer.** The ComfyUI template has it switched on by default. Turn it off when testing these prompts, otherwise you are testing the enhancer's rewrite, not the prompt.

**Testing.** Fixed seed, enhancer off, same resolution and frame rate for every file, so differences come from the prompt alone.

Sources:
- [LTX Prompting Guide (API docs)](https://docs.ltx.io/api-documentation/implementation-guides/prompting-guide)
- [LTX-2.3 Prompt Guide (blog)](https://ltx.io/blog/ltx-2-3-prompt-guide)
- [LTX-2.5 model page (durations, auto duration)](https://docs.ltx.io/models/ltx-2-5)
- [Text-to-Video workflow (distilled template, CFG 1, frame rules)](https://docs.ltx.io/open-source-model/usage-guides/text-to-video)
- [Two-Stage Generation (CFG range for the distilled model)](https://docs.ltx.io/open-source-model/usage-guides/two-stage-generation)
