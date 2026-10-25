# Adapter status

`versions/ltx-2.5/config/adapters.json` is the source of truth for this profile's packaged adapters. Ingredients is integrated as a specialist graph and its LoRA plus BF16 base checkpoint/text encoder are downloaded by default. Its model card identifies the reference-sheet video guide, 1.0 recommended strength, two-part prompt, and 768×448 / 121-frame / 24-fps training bucket.

Other requested adapters remain listed as not provisioned. Their exact LTX-2.5 checkpoint compatibility, graph inputs, and controls must be verified before they appear as enabled switches. A generic LoRA dropdown would not correctly implement IC-LoRA controls. Clean Plate, Restore, and Water Simulation remain excluded.

Set `AUTO_DOWNLOAD_ADAPTERS=false` to defer the entire Ingredients model group during automatic startup. The workflow JSON remains installed but cannot run until those weights are downloaded. No other adapter is exposed as ready. The original workflow and Ingredients defaults total about 108 GiB; use at least a 150 GB container disk to allow the 2 GiB download headroom and working room.

From SSH or the Pod terminal, run the installed Hugging Face download wrappers without passing a token:

```bash
/opt/ltx25-studio/scripts/download-ingredients-models.sh
/opt/ltx25-studio/scripts/download-optional-models.sh
/opt/ltx25-studio/scripts/download-all-models.sh
```

They use the `HF_TOKEN` injected from the RunPod Secret and run the same resumable manifest-based downloader as first-boot provisioning. The optional group currently contains the BF16 Gemma prompt-enhancement model; it is not needed by the original v9 workflow or Ingredients.
