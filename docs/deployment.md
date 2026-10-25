# Build, publish, and deploy

## Build and publish with GitHub Actions

`.github/workflows/build-ghcr.yml` runs CPU-only checks, reads `versions/<id>/profile.json`, builds a `linux/amd64` image, and pushes the profile version tag using the encrypted `GHCR_PACKAGES_PAT` Actions secret. The `ltx-2.5` profile publishes `ghcr.io/acdevmedia/ltx-studio:2.5`. Source the secret from the local `GITHUB_PACKAGES_PAT` in `.env`; the token is used only for registry login, never passed into Docker build or stored in image layers. Hugging Face, AWS, and RunPod credentials are not used by image builds.

Commit and push the project changes, then choose **Actions → Build and publish LTX Studio image → Run workflow** with profile `ltx-2.5` to publish `ghcr.io/acdevmedia/ltx-studio:2.5`. A pushed `v*` Git tag also publishes that release tag and `latest`; use `latest` only for verified releases. Check the build logs and package digest in GHCR. Set the `ltx-studio` package visibility to **Public** for anonymous RunPod pulls.

The workflow requires the repository Actions secret `GHCR_PACKAGES_PAT`, set from `GITHUB_PACKAGES_PAT` in the maintainer's ignored `.env` using GitHub's encrypted secret API or repository settings. Never put the token in source, workflow YAML, a build argument, or an image layer.

## Optional local image build

```bash
docker build --build-arg LTX_VERSION=ltx-2.5 --build-arg CUDA_VERSION=12.8.0 -t ghcr.io/acdevmedia/ltx-studio:dev .
```

The image is Linux/amd64 and requires the NVIDIA container runtime when run. Building can work on a machine with no GPU. RunPod GPU runtime and model generation still need GPU validation.

## Manual GHCR publishing

The local fallback helper reads `GITHUB_PACKAGES_PAT` from the environment or ignored `.env` (key name exactly `GITHUB_PACKAGES_PAT`). Use a dated release tag or semantic version. It tags and pushes only that version tag, authenticates with `docker login --password-stdin`, and never passes the token to Docker build or stores it in the image.

```bash
VERSION=2026.10.24 ./scripts/publish-ghcr.sh
```

`latest` is only pushed when `PUBLISH_LATEST=true`; enable it only after a verified release. The command prints the registry digest to record in the RunPod template. After first push, open the package settings under the `acdevmedia` GitHub organization/user and set container visibility to **Public** so RunPod users can pull without GitHub credentials. Do not paste a token into source code, command arguments, or a workflow file.

## RunPod template

Create/update the template named **LTX 2.5 Distilled ComfyUI Video One-Click** using the versioned image `ghcr.io/acdevmedia/ltx-studio:2.5`. It has a 200 GB container disk, zero persistent volume, an empty start command, no registry credentials, and only HTTP port 8188 for ComfyUI. RunPod provides the browser-based Web terminal from the Pod Connect tab without requiring an exposed app port. Jupyter, SSH, and legacy file-manager ports are not exposed. The request body is versioned in `config/runpod-template.json`; `scripts/create-runpod-template.py` verifies anonymous GHCR pull access and creates or updates it. Add Hugging Face and optional S3 values through RunPod Secrets. Never bake credentials into the image.

Choose **A100 80GB** for the target profile. Use H100/H200 or other CUDA cards only after checking workflow VRAM and kernel compatibility. The 200 GB container disk is temporary; model downloads and outputs do not survive Pod replacement. Enable S3 backup or download needed outputs before stopping the Pod.

## Startup triage

- Missing/unresolved HF secret: create RunPod Secret `HUGGINGFACE_TOKEN`, confirm `HF_TOKEN` resolves, and accept gated-model access. The setup log provides this guidance without logging token values; inspect `/workspace/logs/startup.log`.
- S3 backup reports missing credentials: create RunPod Secrets `S3_ACCESS_KEY_ID` and `S3_SECRET_ACCESS_KEY`, set `S3_BUCKET`, and confirm the template's `RUNPOD_SECRET_*` references resolve. Generation continues while backup is skipped.
- Missing nodes: inspect `/workspace/logs/comfyui.log` for import failures and compare node repositories to the pinned build revisions.
- CUDA unavailable: check the RunPod GPU selection and NVIDIA runtime logs.
- RunPod Connect link returns 403 on an older image digest: paste the proxy URL into a fresh blank tab as a temporary workaround. The republished `2.5` image allows only cross-site top-level GET navigation to `/`; cross-site API calls remain rejected. Existing Pods keep the image digest with which they were created.
- Out of memory or excessive runtime: first reduce duration, base resolution, or decode tile size; measure the exact GPU/workflow combination before changing precision or installing acceleration packages.
- Comparing attention backends: SageAttention is on by default (`COMFYUI_ATTENTION=sage`) after a startup GPU check that falls back to PyTorch attention if it fails. Start a Pod with `COMFYUI_ATTENTION=pytorch` to compare. Export the workflow in API format and run `scripts/benchmark.sh --workflow <name> --resolution 960x544 --frames 721 --prompt-json <file> --fresh` (add `--cold` to include model loading). Each line in `/workspace/logs/benchmarks.jsonl` records seconds per stage (load, text encode, each sampler pass, latent upscale, decode, export), the attention backend, and how many nodes came from cache.
- ComfyUI is healthy but output preview is empty: inspect the workflow's `SaveVideo`/`SaveAudio` node and `/workspace/ComfyUI/output/`.

## Release validation record

Before labeling an image release verified, record the Docker build, package digest, RunPod startup, model provisioning, all seven workflow execution results, MP4/audio playback, S3 tests (if offered), and GPU/memory benchmark. Local static checks alone are not a verified release.
