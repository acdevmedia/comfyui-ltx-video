# ACDEV LTX Studio

ACDEV LTX Studio is a versioned ComfyUI filmmaking environment packaged for RunPod and NVIDIA CUDA GPUs. The first supported profile is **LTX-2.5 Distilled**. It adapts the existing ValyrianTech ComfyUI Docker foundation and keeps the existing advanced LTX filmmaker workflow as the Image to Video starting point.

The project is designed so another model generation can be added as a new profile, for example `versions/ltx-2.6/`, without mixing its checkpoint names, graph files, adapter rules, or dependency pins with 2.5. Runtime code and the container layout are shared; the selected profile supplies version-specific assets and pinned component revisions. A short-clip text-to-video smoke test passed on an A100 80 GB RunPod. Other workflows and the 30-second default still need separate performance validation.

## Quick start for RunPod

Do these steps before starting your first Pod. The template defaults to a **200 GB container disk**. Keep that size if possible; **150 GB is the minimum recommended**. The first launch downloads about 43 GiB of required model files (108 GiB if you enable Ingredients) and needs extra space to complete safely.

1. **Create or sign in to Hugging Face.** Go to [huggingface.co/join](https://huggingface.co/join). Use the account that will receive model access.
2. **Create a read token.** Open [Hugging Face access tokens](https://huggingface.co/settings/tokens), choose **Create new token**, select **Read**, and copy the token. Keep it private.
3. **Agree to the terms for each required model.** While signed in to the same account, open each repository and click **Agree and access**, **Request access**, or the button shown there:
   - [Lightricks LTX-2.5](https://huggingface.co/Lightricks/LTX-2.5)
   - [Comfy-Org Gemma 4](https://huggingface.co/Comfy-Org/gemma-4)
   - [Lightricks Ingredients IC-LoRA](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Ingredients)

   Approvals are separate. Make sure you have access to each repository before launching.
4. **Add the token to RunPod Secrets.** In RunPod, open **Settings → Secrets** and create a secret named exactly `HUGGINGFACE_TOKEN`. Paste the token as its value. The template connects this secret automatically; never put the token in a public field.
5. **Launch the template.** Choose **LTX 2.5 Distilled ComfyUI Video One-Click**, select an NVIDIA GPU (A100 80 GB is recommended), and keep the container disk at its **200 GB default**. If you change it, select **at least 150 GB**. No persistent volume is used.
6. **Wait for setup to finish.** First launch downloads about 43 GiB of models (more if Ingredients is enabled). Open the Pod's **Logs** tab and wait until it says ComfyUI is ready. Do not stop the Pod while files are downloading.
7. **Open ComfyUI.** In the Pod's **Connect** tab, click the HTTP service for port **8188 / ComfyUI**. The workflows are installed automatically; Image to Video opens first.

The container disk is temporary, so download videos you want to keep before stopping or replacing the Pod, or configure optional S3 backup. If startup says a repository is gated, approve that exact repository using the same Hugging Face account as your token. If the token is missing, check that the RunPod Secret is named `HUGGINGFACE_TOKEN`. See [the template guide](config/runpod-template.md) for settings and optional backup details.

## Repository guide

| Path | Purpose |
|---|---|
| `Dockerfile`, `.dockerignore` | CUDA builder/runtime image based on the copied ValyrianTech deployment approach. No model weights are baked into the image. |
| `versions/<ltx-version>/profile.json` | Version identity, defaults, model/workflow paths, application revisions, and dependency pins. |
| `versions/<ltx-version>/config/models.json` | Hugging Face repositories, exact files, destinations, and workflow requirements for that model version. |
| `versions/<ltx-version>/config/adapters.json` | Compatible adapters, activation state, and specialist conditioning details for that version. |
| `versions/<ltx-version>/workflows/` | The ten packaged filmmaker graphs plus the preserved v9 master source for LTX-2.5. |
| `archive/official-workflow-references/` | Official graph references used to validate LTX conditioning behavior; these are engineering references, not the user-facing interface. |
| `archive/v2v-workflow-sources/` | Editable UI graphs for workflows 08-10, converted by the installed ComfyUI frontend from `scripts/v2v_graphs.py`. |
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

`versions/ltx-2.5/profile.json` is the source of truth for this profile. It pins the ComfyUI core and node repositories, Python package versions, Torch/CUDA combination, workflow list, default graph, and generation defaults. The short-clip A100 smoke test is not a full performance or seven-workflow validation; see the compatibility notes in the profile before relying on long clips or other modes.

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
| `08_LTX25_Extend_After.json` | Upload a clip and continue it: the model is shown real frames from the clip's ending, and the saved MP4 is the original plus the new section, with sound. GPU-tested. |
| `09_LTX25_Extend_Before.json` | Upload a clip and generate a lead-in that runs straight into its first frame; saves the new section plus the original, with sound. GPU-tested. |
| `10_LTX25_New_Angle.json` | Coverage for editing: re-stages a moment of an uploaded clip from a new camera position described in the prompt, locked to the clip's original sound. Needs an uploaded reference sheet and the Ingredients models. GPU-tested. |

The standard video defaults are 30 seconds, 24 fps, 721 frames, 16:9, and 0.5 megapixels. LTX video frame counts must satisfy `frames % 8 == 1`. These are requested defaults, not a claim that every mode, GPU, or pod can render that duration efficiently. Ingredients intentionally uses the documented 121-frame, 768×448 training bucket and is a single-stage workflow. Shorten clips or resolution if the selected GPU needs it. The [LTX ComfyUI documentation](https://docs.ltx.io/open-source-model/integration-tools/comfy-ui) and [Ingredients model card](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Ingredients) are linked for current technical constraints.

### Model downloads and storage

Startup downloads the INT8 ConvRot models shared by workflows 01–06. The Ingredients BF16 checkpoints/IC-LoRA are opt-in (`AUTO_DOWNLOAD_ADAPTERS=true` or `scripts/download-ingredients-models.sh`), and the separate BF16 prompt-enhancement encoder is optional. The table lists approximate on-disk sizes reported by a successful RunPod A100 first launch; Hugging Face metadata and filesystem rounding can cause small differences. The core workflow set is about **43.18 GiB**, Ingredients adds **64.81 GiB** when enabled, for about **107.99 GiB** with both. The optional BF16 prompt-enhancement encoder adds **9.57 GiB**. The template uses a **200 GB container disk** for the default model set, download headroom, temporary cache, and outputs. Do not stop startup preflight by deleting model files.

| Group | ComfyUI model folder | SafeTensors file | Download size |
|---|---|---|---:|
| Core | `diffusion_models/` | `ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors` | 20.03 GiB |
| Core | `text_encoders/` | `gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors` | 14.32 GiB |
| Core | `text_encoders/` | `gemma4_e2b_it_int8_convrot.safetensors` | 4.84 GiB |
| Core | `vae/` | `ltx-2.5-video-vae-conv-bf16.safetensors` | 1.35 GiB |
| Core | `vae/` | `ltx-2.5-video-vae-bf16.safetensors` | 1.37 GiB |
| Core | `vae/` | `ltx-2.5-audio-vae-bf16.safetensors` | 0.34 GiB |
| Core | `latent_upscale_models/` | `ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors` | 0.93 GiB |
| Ingredients | `diffusion_models/` | `ltx-2.5-22b-distilled-transformer-bf16.safetensors` | 39.13 GiB |
| Ingredients | `text_encoders/` | `gemma4-12b-with-proj-ltx-2.5-bf16.safetensors` | 24.46 GiB |
| Ingredients | `loras/` | `ltx-2.5-22b-ic-lora-ingredients-0.9.safetensors` | 1.22 GiB |
| Optional | `text_encoders/` | `gemma4_e2b_it_bf16.safetensors` | 9.57 GiB |

The default startup total is Core only; Ingredients is opt-in and the optional file is not needed by the default filmmaker workflows. Selecting all declared files brings the total to about **117.56 GiB**.

Optional Hugging Face downloads can be run from the Pod's SSH or terminal session; the `HF_TOKEN` RunPod Secret is used automatically and should not be passed on the command line:

```bash
/opt/ltx25-studio/scripts/download-ingredients-models.sh
/opt/ltx25-studio/scripts/download-optional-models.sh
/opt/ltx25-studio/scripts/download-all-models.sh
```

The first command fetches the Ingredients model group, the second fetches only files marked optional in the profile manifest, and the third fetches every declared model. Each command checks free disk space before downloading. See [adapter/download groups](docs/adapters.md).

See [workflow details](docs/workflows.md), [adapter compatibility](docs/adapters.md), and [official graph sources](LICENSES/WORKFLOW_REFERENCES.md).

## RunPod template and advanced setup

The public template recommends an **NVIDIA A100 80 GB**, uses a 200 GB temporary container disk, and has no persistent volume. H100/H200 and RTX PRO GPUs may work, but performance and compatibility vary. Startup provisions models and workflows automatically; no terminal commands, manual downloads, workflow imports, or ComfyUI restarts are required. The template exposes only HTTP `8188` for ComfyUI. RunPod provides its browser-based Web terminal directly from the Pod Connect tab, with no additional app port. Jupyter, SSH, and legacy file-manager ports are not exposed. See [the template guide](config/runpod-template.md) for the full settings and [.env.example](.env.example) for configuration names. Never commit or share secret values.

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
| `AUTO_DOWNLOAD_ADAPTERS` | `false` | Include Ingredients BF16 checkpoints and IC-LoRA (65 GiB) in startup provisioning. Only workflow 07 needs them. |
| `MODEL_DOWNLOAD_WORKERS` | `3` | Number of model files downloaded concurrently. |
| `COMFYUI_ATTENTION` | `sage` | `sage` uses SageAttention after a startup GPU check (falls back to PyTorch if it fails); `pytorch` forces PyTorch attention for comparison. |
| `HF_HOME` | `/workspace/.cache/huggingface` | Persistent Hub cache location. |
| `HF_TOKEN` | empty | Hugging Face read token for gated model downloads. |
| `HUGGING_FACE_HUB_TOKEN` | empty | Alternate name for `HF_TOKEN`. `HF_TOKEN` takes precedence. |
| `TINI_SUBREAPER` | `1` | Registers Tini as a child subreaper when the upstream launcher runs it outside PID 1. |

### Optional access services

| Variable | Default | Purpose |
|---|---:|---|
| `ENABLE_JUPYTER` | `false` | Optional for custom deployments; Jupyter is not exposed by the standard RunPod template. |
| `JUPYTER_TOKEN` | empty | Required only when Jupyter is enabled in a custom deployment. |
| `PUBLIC_KEY` | empty | Optional SSH key for custom deployments; the standard template uses RunPod Web terminal instead. |
| `AI_TOOLKIT_AUTH` | empty | Optional upstream AI Toolkit authentication; not used by the standard template. |

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

The recommended image build is GitHub Actions; this avoids requiring a local NVIDIA GPU or a large local Docker disk. The workflow in `.github/workflows/build-ghcr.yml` runs CPU-only checks, reads the selected LTX profile, builds a Linux/amd64 image, and publishes a versioned image tag. The current RunPod template uses `ghcr.io/acdevmedia/ltx-studio:2.5` (LTX-2.5 profile). It uses the encrypted `GHCR_PACKAGES_PAT` Actions secret sourced from the local `GITHUB_PACKAGES_PAT`; the credential is used only for GHCR registry authentication and never enters Docker build layers. Hugging Face and S3 credentials are never used by the image build.

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

See [release and deployment notes](docs/deployment.md). Do not label the image or `latest` as verified until a RunPod GPU run covers model provisioning, all ten workflows, audio/video playback, backup behavior when offered, and benchmark measurements.

## Startup logs

Startup prints a plain-language summary followed by six numbered checks: Hugging Face access, GPU/CUDA, required model downloads, workflow verification, optional backup/thumbnail services, and ComfyUI startup. A final `[ready]` message appears only after ComfyUI answers its local `/system_stats` health request. If startup fails, the log names the failed step and points to the relevant detail file. Logs are stored in `/workspace/logs/startup.log`, `/workspace/logs/comfyui.log`, `/workspace/logs/nginx.log`, and, when enabled, `/workspace/logs/backup.log`. Credential values are never included.

## Troubleshooting

- **Missing or denied models:** accept the gated terms, confirm token read access, and inspect `/workspace/logs/startup.log`. Distinct messages identify missing token, denied access/gated acceptance, unavailable repository/file, network failure, and low disk.
- **RunPod Connect opens ComfyUI with HTTP 403:** an older image digest's ComfyUI browser-origin guard rejects a dashboard-launched cross-site page navigation. As a temporary workaround, open a fresh blank tab and paste the full `https://<pod-id>-8188.proxy.runpod.net` URL into the address bar. The republished `2.5` image permits only that safe top-level page navigation; cross-site API and form requests remain blocked. Existing Pods keep their original image digest.
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
