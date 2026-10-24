# Adapter status

`versions/ltx-2.5/config/adapters.json` is the source of truth for this profile's packaged adapters. Ingredients is integrated as a specialist graph and downloaded by default. Its model card identifies the reference-sheet video guide, BF16 base checkpoint/text encoder, 1.0 recommended strength, two-part prompt, and 768×448 / 121-frame / 24-fps training bucket.

Other requested adapters remain listed as not provisioned. Their exact LTX-2.5 checkpoint compatibility, graph inputs, and controls must be verified before they appear as enabled switches. A generic LoRA dropdown would not correctly implement IC-LoRA controls. Clean Plate, Restore, and Water Simulation remain excluded.

Set `AUTO_DOWNLOAD_ADAPTERS=false` to skip downloading the Ingredients LoRA weight. The workflow JSON remains installed but cannot run until the weight is present. No other adapter is exposed as ready.
