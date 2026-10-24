# Architecture

The image is a trimmed adaptation of the ValyrianTech Docker foundation. The upstream Docker source is preserved; this repository has its own adapted, multi-stage Dockerfile. A profile ID such as `ltx-2.5` selects model files, workflows, defaults, node revisions, and Python pins. The 2.5 profile currently uses CUDA 12.8 and PyTorch 2.8.0. The image keeps RunPod shell/SSH support, optional JupyterLab, FFmpeg, and persistent workspace behavior. It excludes model weights and unrelated model-serving software.

For LTX-2.5, `versions/ltx-2.5/profile.json` pins build components:

| Component | Revision |
|---|---|
| ComfyUI | `06c67806` (the revision referenced by the existing working setup script) |
| ComfyUI Manager | `7e1af9c202fbd0051df3da43572976acd12857dc` |
| ComfyUI Custom Scripts | `609f3afaa74b2f88ef9ce8d939626065e3247469` |
| ComfyUI-LTXVideo | `220e1d45aa0469f518e982102fca4dca92a61862` |
| Python dependencies | Exact package versions in `versions/ltx-2.5/profile.json` |

The application and custom nodes live under `/opt/ltx25-studio/ComfyUI` in the image. `--input-directory`, `--output-directory`, `--user-directory`, and the extra model-path configuration direct mutable data to `/workspace/ComfyUI`. The image build sets `LTX_VERSION` and resolves that profile's model manifest and workflow source. Workflows are copied only when absent, so a restart does not replace user workflows. Model files, inputs, outputs, logs, cache, and instance state remain on the persistent volume.

Startup sequence: workspace initialization → CUDA access check → model provisioning / verification → workflow JSON verification → optional backup and Jupyter startup → ComfyUI. Docker health is based on ComfyUI's `/system_stats`. Since startup waits for model provisioning, health does not report ready while initial downloads are incomplete.

The local volume is not populated by Docker layers. This avoids the `/workspace` mount shadowing baked assets. On startup, the installer selects the profile's initial filmmaker graph and copies it to the ComfyUI default template location.

## Adding an LTX generation

Copy a profile to `versions/<new-id>/`, then update its profile metadata, exact model manifest, adapter manifest, workflow assets, dependency pins, and compatibility record. Workflow verification reads the file list from the selected profile. The build argument helper exports that profile's CUDA and version identifiers for CI. Build a separate image from the selected profile; do not switch profiles in a running container unless its image was built for that profile.
