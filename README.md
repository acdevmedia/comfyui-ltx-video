# ACDEV LTX Studio

ACDEV LTX Studio is a versioned ComfyUI filmmaking environment packaged for RunPod and NVIDIA CUDA GPUs. The first supported profile is **LTX-2.5 Distilled**. It adapts the existing ValyrianTech ComfyUI Docker foundation and keeps the existing advanced LTX filmmaker workflow as the Image to Video starting point.

The project is designed so another model generation can be added as a new profile, for example `versions/ltx-2.6/`, without mixing its checkpoint names, graph files, adapter rules, or dependency pins with 2.5. Runtime code and the container layout are shared; the selected profile supplies version-specific assets and pinned component revisions.

## Repository guide

| Path | Purpose |
|---|---|
| `Dockerfile`, `.dockerignore` | CUDA builder/runtime image based on the copied ValyrianTech deployment approach. No model weights are baked into the image. |
| `versions/<ltx-version>/profile.json` | Version identity, defaults, model/workflow paths, application revisions, and dependency pins. |
| `versions/<ltx-version>/config/models.json` | Hugging Face repositories, exact files, destinations, and workflow requirements for that model version. |
| `versions/<ltx-version>/config/adapters.json` | Compatible adapters, activation state, and specialist conditioning details for that version. |
| `versions/<ltx-version>/workflows/` | The seven packaged filmmaker graphs plus the preserved v9 master source for LTX-2.5. |
| `archive/official-workflow-references/` | Official graph references used to validate LTX conditioning behavior; these are engineering references, not the user-facing interface. |
| `docker/` | Startup orchestration, persistent workspace setup, ComfyUI launch, and health checks. |
| `scripts/` | Workflow generation/installation, model provisioning and checks, profile build arguments, diagnostics, GHCR publishing, and benchmarks. |
| `backup/` | Optional real-time, one-shot, and verification tools for S3-compatible output backup. |
| `frontend/video-gallery/` | ComfyUI extension for browser playback and the FFmpeg poster thumbnail service. |
| `tests/` | CPU-only static checks. GPU generation and cloud integrations are separate acceptance checks. |
| `config/runpod-template.md` | RunPod template fields and recommended initial configuration. |
| `docs/` | Architecture, workflow, adapter, storage, and deployment details. |
| `LICENSES/` | Upstream copyright/license notices and workflow reference attribution. |
| `scene_prompts/`, `config_prompts/`, `GPT-images/` | Preserved prompt examples and project reference material. |

The ignored local `.env` is only for local tooling. Do not commit it, put it in a Docker build argument, or paste secrets into a workflow. `.env.example` contains names and non-secret defaults only.

## Current version profile

`versions/ltx-2.5/profile.json` is the source of truth for this profile. It pins the ComfyUI core and node repositories, Python package versions, Torch/CUDA combination, workflow list, default graph, and generation defaults. The profile also marks GPU execution as unverified until tested on RunPod.

To add a future model generation:

1. Copy the closest compatible profile directory to a new ID such as `versions/ltx-2.6/`.
2. Update `profile.json` first: ID, product name, checkpoint family, default workflow, compatibility notes, CUDA/Torch/Python requirements, and exact ComfyUI/node commits.
3. Replace `config/models.json` with the new version's exact repositories, filenames, and paths. Keep separate INT8/BF16 entries when a graph requires different checkpoints.
4. Review every entry in `config/adapters.json`; only mark an adapter enabled after its model card and conditioning graph match the new checkpoint.
5. Add and validate version-specific workflows. Do not reuse 2.5 graphs or model filenames without checking node/API changes and conditioning requirements.
6. Run the CPU-only profile and workflow checks, build with that profile, then validate startup and each generation mode on a compatible RunPod GPU before publishing it as a verified release.

`scripts/profile-build-args.py --version ltx-2.5` reports the build inputs consumed by GitHub Actions. The Docker build reads the selected profile to check CUDA compatibility and pin the relevant component revisions and packages.

## LTX-2.5 filmmaker interfaces

The default **Image to Video — Filmmaker** workflow is derived from `LTX25_Filmmaker_Workflow_v9_Advanced.json`; that interface and graph remain the project authority. Official LTX workflows are retained as references for correct model loading and conditioning.

| Workflow file | Interface |
|---|---|
| `01_LTX25_Image_to_Video.json` | Opening image, scene prompt, optional prompt rewrite, negative prompt, two-stage render, resolution, guidance, seed, audio, and export controls. Default graph. |
| `02_LTX25_Text_to_Video.json` | Text-only two-stage video generation without image-input dependencies. |
| `03_LTX25_First_Last_Frame.json` | Independent opening and closing frame inputs using LTX first/last-frame conditioning. |
| `04_LTX25_Audio_to_Video.json` | Audio-conditioned video with optional opening frame; the supplied soundtrack is preserved and muxed into the result. |
| `05_LTX25_Text_to_Audio.json` | Audio-only generation and audio export. |
| `06_LTX25_Two_Stage_Advanced.json` | Detailed control of base generation, upscale, and enhancement stages. |
| `07_LTX25_Ingredients.json` | Specialist Ingredients IC-LoRA conditioning for repeatable character, prop, costume, and location references. |

The standard video defaults are 30 seconds, 24 fps, 721 frames, 16:9, and 0.5 megapixels. LTX video frame counts must satisfy `frames % 8 == 1`. These are requested defaults, not a claim that every mode, GPU, or pod can render that duration efficiently. Ingredients intentionally uses the documented 121-frame, 768×448 training bucket and is a single-stage workflow. Shorten clips or resolution if the selected GPU needs it. The [LTX ComfyUI documentation](https://docs.ltx.io/open-source-model/integration-tools/comfy-ui) and [Ingredients model card](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Ingredients) are linked for current technical constraints.

### Model downloads and storage

Startup downloads the original v9 filmmaker workflow's INT8 ConvRot models and the Ingredients BF16 checkpoints/IC-LoRA. Other model files, including the separate BF16 prompt-enhancement encoder, are optional. The full default set is about **108 GiB**, plus 2 GiB preflight headroom, so the current 100 GB container-disk setting is too small. Use a **150 GB container disk** to provision the original workflow and Ingredients together. Do not stop startup preflight by deleting model files.

Optional Hugging Face downloads can be run from the Pod's SSH or terminal session; the `HF_TOKEN` RunPod Secret is used automatically and should not be passed on the command line:

```bash
/opt/ltx25-studio/scripts/download-ingredients-models.sh
/opt/ltx25-studio/scripts/download-optional-models.sh
/opt/ltx25-studio/scripts/download-all-models.sh
```

The first command fetches the Ingredients model group, the second fetches only files marked optional in the profile manifest, and the third fetches every declared model. Each command checks free disk space before downloading. See [adapter/download groups](docs/adapters.md).

See [workflow details](docs/workflows.md), [adapter compatibility](docs/adapters.md), and [official graph sources](LICENSES/WORKFLOW_REFERENCES.md).

## RunPod launch

Recommended initial target: **NVIDIA A100 80 GB**. H100/H200 and RTX PRO GPUs may be suitable, but throughput, attention kernels, memory use, and compatibility must be checked for the chosen graph. This repository has not verified generation on any GPU yet.

1. Sign in to Hugging Face and accept the gated LTX-2.5 model terms for the account used by your token.
2. Select **LTX 2.5 Distilled ComfyUI Video One-Click**. Create a RunPod Secret named `HUGGINGFACE_TOKEN`; the template injects it into `HF_TOKEN` using `{{ RUNPOD_SECRET_HUGGINGFACE_TOKEN }}`.
3. The template uses a 100 GB container disk and no persistent volume. Container files, models, and outputs are temporary and may be lost when the Pod is stopped or replaced. Download valuable outputs or enable S3 backup.
4. The alternate `HUGGING_FACE_HUB_TOKEN` name is accepted if you prefer that variable.
5. For backup, create RunPod Secrets named `S3_ACCESS_KEY_ID` and `S3_SECRET_ACCESS_KEY`, set the bucket and other S3 variables, then set `REALTIME_BACKUP=true`.
6. The template exposes HTTP `8188`, `8888`, `8675`, TCP `22`, `8080`, and UDP `22`, `8080`, matching the source ComfyUI template. Jupyter remains disabled by default. Start the pod and open ComfyUI after provisioning reaches readiness.

> **Important: approve every gated model repository separately.** Accepting the LTX-2.5 base-model terms does not automatically grant access to the Ingredients IC-LoRA or any other gated adapter repository. Before launching, open each gated repository page while signed into the same Hugging Face account used for `HUGGINGFACE_TOKEN` and click **Agree and Access**. The required [Ingredients repository](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Ingredients) has its own access agreement. If provisioning reports that a repository is gated, accept that repository's terms and restart the Pod; the exact repository is shown in `/workspace/logs/startup.log`.

There is no manual login, script run, model download, workflow import, or restart. Startup initializes `/workspace`, checks CUDA, downloads missing models, verifies workflows, then starts ComfyUI. On this no-volume template, models and outputs are not persistent across Pod replacement. Provisioning errors are written to `/workspace/logs/startup.log`.

RunPod settings, ports, and environment recommendations are listed in [the template guide](config/runpod-template.md). The full configuration example is [.env.example](.env.example); copy its values into RunPod's UI individually, and leave secrets out of local and committed files.

## Environment variables

### Profile and generation

| Variable | Default | Purpose |
|---|---:|---|
| `LTX_VERSION` | `ltx-2.5` | Version profile packaged into this image. Do not override it to another profile unless the image was built for that profile. |
| `COMFYUI_PORT` | `8188` | ComfyUI listener. |
| `LTX_DEFAULT_WORKFLOW` | profile default | Workflow opened by default. |
| `LTX_DEFAULT_DURATION` | `30` | Desired video duration in seconds; Ingredients retains its trained five-second default. |
| `LTX_DEFAULT_FPS` | `24` | Video frame rate. |
| `LTX_DEFAULT_MEGAPIXELS` | `0.5` | Starting video resolution budget. |
| `LTX_DEFAULT_ASPECT_RATIO` | `16:9` | Supported values include 16:9, 9:16, 4:3, 1:1, and 21:9. |
| `AUTO_DOWNLOAD_MODELS` | `true` | Provision missing default model files at startup. |
| `AUTO_DOWNLOAD_ADAPTERS` | `true` | Include Ingredients BF16 checkpoints and IC-LoRA in default startup provisioning. Set false to defer that model group. |
| `HF_HOME` | `/workspace/.cache/huggingface` | Persistent Hub cache location. |
| `HF_TOKEN` | empty | Hugging Face read token for gated model downloads. |
| `HUGGING_FACE_HUB_TOKEN` | empty | Alternate name for `HF_TOKEN`. `HF_TOKEN` takes precedence. |

### Optional access services

| Variable | Default | Purpose |
|---|---:|---|
| `ENABLE_JUPYTER` | `false` | Enable Jupyter on port 8888. |
| `JUPYTER_TOKEN` | empty | Required if Jupyter is enabled. |
| `PUBLIC_KEY` | empty | Optional SSH authorized key; SSH server is started only when supplied. |
| `AI_TOOLKIT_AUTH` | RunPod secret reference | Preserved from the upstream template for its optional AI Toolkit service. |
| `DOWNLOAD_FLUX`, `DOWNLOAD_WAN` | `false` | Preserved upstream switches; both remain disabled in this LTX-only image. |

### S3-compatible output backup

| Variable | Default | Purpose |
|---|---:|---|
| `REALTIME_BACKUP` | `false` | Enable the non-deleting background watcher. |
| `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | empty | S3-compatible access credentials. |
| `S3_BUCKET` | empty | Destination bucket. |
| `S3_ENDPOINT_URL` | `https://sfo3.digitaloceanspaces.com` | S3 endpoint; defaults to DigitalOcean SFO3. |
| `S3_FORCE_PATH_STYLE` | `false` | Enable path-style addressing for providers that require it. |
| `S3_PREFIX` | `ltx25-studio` | Object prefix. |
| `S3_REGION` | `sfo3` | Signing region; defaults to DigitalOcean SFO3. |
| `S3_SECRET_ACCESS_KEY` | empty | S3-compatible secret key. |
| `S3_SESSION_TOKEN` | empty | Optional temporary credential token. |
| `S3_SSE`, `S3_STORAGE_CLASS` | `none`, `STANDARD` | Optional encryption and storage class. |
| `BACKUP_SOURCE_DIR` | `/workspace/ComfyUI/output` | Eligible output directory. |
| `BACKUP_RECHECK_SECONDS` | `120` | Reconciliation interval. |
| `BACKUP_SETTLE_SECONDS` | `8` | Minimum file-stability interval before upload. |
See [storage setup and commands](docs/storage.md) for AWS, Spaces, MinIO, one-shot backup, verification, logs, and key layout.

## Outputs and browser previews

ComfyUI saves output under `/workspace/ComfyUI/output/`. The **Videos & Audio** browser panel plays recent MP4/WebM/MOV and audio files in an HTML5 control, supports nested folders, and links to the original. A background FFmpeg helper creates cached JPEG poster images for completed videos. ComfyUI history remains the source list; the panel requests only the latest 100 jobs when opened and refreshes after generation. Outputs and posters persist with `/workspace`.

## Build, test, and publish

The recommended image build is GitHub Actions; this avoids requiring a local NVIDIA GPU or a large local Docker disk. The workflow in `.github/workflows/build-ghcr.yml` runs CPU-only checks, reads the selected profile, builds a Linux/amd64 image, and publishes the profile version tag, such as `ghcr.io/acdevmedia/ltx-studio:2.5`. It uses the encrypted `GHCR_PACKAGES_PAT` Actions secret sourced from the local `GITHUB_PACKAGES_PAT`; the credential is used only for GHCR registry authentication and never enters Docker build layers. Hugging Face and S3 credentials are never used by the image build.

To start a build after this repository change is committed and pushed:

- Use **Actions → Build and publish LTX Studio image → Run workflow** with profile `ltx-2.5` to publish `ghcr.io/acdevmedia/ltx-studio:2.5`.
- Push a release tag such as `v2.5.0` after the chosen validation gate. The tag build pushes `2.5`, `v2.5.0`, and `latest` after the CPU checks pass.
- Check the workflow run and package digest in GHCR. Make `ghcr.io/acdevmedia/ltx-studio` public in package settings before RunPod anonymous pulls.

After the versioned image is anonymously pullable from GHCR, create or update the public RunPod template from `config/runpod-template.json`:

```bash
python3 scripts/create-runpod-template.py --image ghcr.io/acdevmedia/ltx-studio:2.5
```

The helper reads `RUNPOD_API_KEY` from the shell or ignored `.env`, verifies anonymous GHCR pulls, and applies labeled ports and the complete environment list. Replace placeholder values with RunPod Secrets where appropriate.

The local build remains available for systems with enough disk:

```bash
docker build --build-arg LTX_VERSION=ltx-2.5 --build-arg CUDA_VERSION=12.8.0 \
  -t ghcr.io/acdevmedia/ltx-studio:dev .
```

Static checks (no GPU required):

```bash
python3 scripts/package-workflows.py
bash tests/test-startup.sh
python3 tests/test-models.py
python3 tests/test-workflows.py
bash tests/test-backup.sh
bash tests/test-secrets.sh
```

See [release and deployment notes](docs/deployment.md). Do not label the image or `latest` as verified until a RunPod GPU run covers model provisioning, all seven workflows, audio/video playback, backup behavior when offered, and benchmark measurements.

## Troubleshooting

- **Missing or denied models:** accept the gated terms, confirm token read access, and inspect `/workspace/logs/startup.log`. Distinct messages identify missing token, denied access/gated acceptance, unavailable repository/file, network failure, and low disk.
- **ComfyUI does not become ready:** provisioning happens before ComfyUI starts. Read `startup.log` and `comfyui.log`; missing files or node import errors should be resolved before generation.
- **CUDA unavailable:** select a CUDA NVIDIA GPU pod and verify the RunPod GPU runtime. This laptop has no NVIDIA card; local container generation has not been attempted.
- **Out of GPU memory or slow render:** reduce resolution, duration, or decode workload. Record the GPU, graph, frame count, elapsed time, and peak memory before changing precision or adding acceleration libraries.
- **No browser output:** confirm a video/audio save node completed and inspect `/workspace/ComfyUI/output/`; then refresh the panel. Poster generation is separate from MP4 playback.
- **Backup misconfiguration:** ComfyUI continues when backup is disabled or fails to configure. Inspect `/workspace/logs/backup.log`, then run `backup/verify-backup.sh` with the same environment variables.
- **Workflow file upgrades:** packaged workflow copies are installed only if absent. Existing persistent workflows are preserved; remove or rename a user's workflow manually only when they explicitly want a fresh packaged copy.

## License and attribution

The Docker and RunPod service layout is adapted from [ValyrianTech/ComfyUI_with_Flux](https://github.com/ValyrianTech/ComfyUI_with_Flux). The upstream repository is not modified. ComfyUI and each custom node retain their upstream license; copies and reference links are in `LICENSES/`. LTX model weights are downloaded by the user-authorized Hugging Face account under the applicable Lightricks terms. Read and accept those terms before deployment.

## Verification record

The repository includes CPU-only tests and GPU/cloud acceptance instructions. A local NVIDIA card is unavailable, so container startup with CUDA, RunPod generation, HF gated downloads, actual S3 upload, and browser playback of generated output remain unverified until their respective environments are used. Never infer success for those steps from a successful static test or image build.
