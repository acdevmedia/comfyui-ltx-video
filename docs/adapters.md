# Adapter status

`versions/ltx-2.5/config/adapters.json` is the source of truth for this profile's packaged adapters. Ingredients is integrated as a specialist graph and its LoRA plus BF16 base checkpoint/text encoder are opt-in downloads (about 65 GiB). Its model card identifies the reference-sheet video guide, 1.0 recommended strength, two-part prompt, and 768×448 / 121-frame / 24-fps training bucket.

Scene Transition, CrossView Prompt, Relight and Day to Night are also integrated: see [the workflow guide](workflows.md#new-camera-angle-relight-and-day-to-night). Scene Transition, CrossView and Relight are LTX-2.3 files with no 2.5 build, so `adapters.json` marks them `base_model: ltx-2.3`; they are enabled and labelled unproven, not verified.

| Adapter | Licence | Gated | Revision and size pinned | SHA256 pinned |
|---|---|---|---|---|
| Scene Transition | Apache 2.0 | No | Yes | Yes |
| CrossView Prompt | Apache 2.0 | No | Yes | Yes |
| Relight | LTX-2 Community License | Yes | Yes | Yes |
| Day to Night | LTX-2.x Community License | Yes | Yes | Yes |

Accept each gated repository's terms with the Hugging Face account behind `HF_TOKEN`. Hugging Face hides a gated file's hash until then, so to add another gated LoRA, set its `sha256` to `null`, accept the licence and run `python3 scripts/pin-gated-models.py`. It reads `HF_TOKEN` from the shell or the ignored `.env`, never prints it, and also confirms the hashes already pinned. The community licences need a separate commercial licence for companies with annual revenue of $10 million or more.

Other requested adapters remain listed as not provisioned. Their exact LTX-2.5 checkpoint compatibility, graph inputs, and controls must be verified before they appear as enabled switches. A generic LoRA dropdown would not correctly implement IC-LoRA controls. Clean Plate, Restore, and Water Simulation remain excluded.

The default INT8 workflows do not need the BF16 stack, so `AUTO_DOWNLOAD_ADAPTERS` defaults to `false`. Set it to `true` to provision the Ingredients group at startup, or run the script below. Workflows 11 to 13 use the same stack and need `download-adapter-models.sh`, which is never run automatically, so a licence you have not accepted cannot stop a Pod starting. Each workflow JSON remains installed but cannot run until its weights are downloaded. The core set is about 43 GiB and about 108 GiB with Ingredients; the RunPod template uses a 200 GB container disk to allow the 2 GiB download headroom, temporary cache, and outputs.

From SSH or the Pod terminal, run the installed Hugging Face download wrappers without passing a token:

```bash
/opt/ltx25-studio/scripts/download-ingredients-models.sh
/opt/ltx25-studio/scripts/download-adapter-models.sh
/opt/ltx25-studio/scripts/download-optional-models.sh
/opt/ltx25-studio/scripts/download-all-models.sh
```

They use the `HF_TOKEN` injected from the RunPod Secret and run the same resumable manifest-based downloader as first-boot provisioning. The optional group currently contains the BF16 Gemma prompt-enhancement model; it is not needed by the original v9 workflow or Ingredients.
