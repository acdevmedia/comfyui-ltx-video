# Build, publish, and deploy

## Build and publish with GitHub Actions

`.github/workflows/build-ghcr.yml` runs CPU-only checks, reads `versions/<id>/profile.json`, builds a `linux/amd64` image, and pushes the version tag (for example, `2.5`) using the encrypted `GHCR_PACKAGES_PAT` Actions secret. Source it from the local `GITHUB_PACKAGES_PAT` in `.env`; the token is used only for registry login, never passed into Docker build or stored in image layers. Hugging Face, AWS, and RunPod credentials are not used by image builds.

Commit and push the project changes, then choose **Actions → Build and publish LTX Studio image → Run workflow**. Use profile `ltx-2.5` to publish `ghcr.io/acdevmedia/ltx-studio:2.5`. A pushed `v*` Git tag also publishes that release tag and `latest`; use `latest` only for verified releases. Check the build logs and package digest in GHCR. Set the `ltx-studio` package visibility to **Public** for anonymous RunPod pulls.

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

Create a template named **ACDEV LTX-2.5 Studio** with the immutable image tag, 100 GB container disk, a 250 GB persistent volume mounted at `/workspace`, HTTP ports 8188 and 8080, optional HTTP 8888 for Jupyter, and optional TCP 22 for SSH. The public request body is versioned in `config/runpod-template.json`; `scripts/create-runpod-template.py` verifies anonymous GHCR pull access and creates it through the RunPod REST API. Add Hugging Face and S3 values through RunPod Secrets. Never bake credentials into the template or image.

Choose **A100 80GB** for the target profile. Use H100/H200 or other CUDA cards only after checking workflow VRAM and kernel compatibility. Volume recommendation is 200GB minimum and 250GB preferred for the provisioned INT8+BF16 set plus outputs/cache.

## Startup triage

- Missing gated weights: verify token permissions and account acceptance; inspect `/workspace/logs/startup.log`.
- Missing nodes: inspect `/workspace/logs/comfyui.log` for import failures and compare node repositories to the pinned build revisions.
- CUDA unavailable: check the RunPod GPU selection and NVIDIA runtime logs.
- Out of memory or excessive runtime: first reduce duration, base resolution, or decode tile size; measure the exact GPU/workflow combination before changing precision or installing acceleration packages.
- ComfyUI is healthy but output preview is empty: inspect the workflow's `SaveVideo`/`SaveAudio` node and `/workspace/ComfyUI/output/`.

## Release validation record

Before labeling an image release verified, record the Docker build, package digest, RunPod startup, model provisioning, all seven workflow execution results, MP4/audio playback, S3 tests (if offered), and GPU/memory benchmark. Local static checks alone are not a verified release.
