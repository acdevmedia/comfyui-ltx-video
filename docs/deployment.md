# Build, publish, and deploy

## Build and publish with GitHub Actions

`.github/workflows/build-ghcr.yml` runs CPU-only checks, reads `versions/<id>/profile.json`, builds a `linux/amd64` image, and pushes it with the short-lived repository `GITHUB_TOKEN`. In the `ltx-studio` package settings, set visibility to **Public** and grant repository `acdevmedia/comfyui-ltx-video` **Write** access under **Manage Actions access**. This one-time package permission is required because GHCR package permissions are granular. Hugging Face, AWS, and RunPod credentials are not used by image builds.

Commit and push the project changes, then choose **Actions → Build and publish LTX Studio image → Run workflow**. Use the profile ID `ltx-2.5` for this project. A manual run creates `ghcr.io/acdevmedia/ltx-studio:2.5` and an immutable `sha-<12 chars>` image. A pushed `v*` Git tag creates that release tag, the SHA tag, and `latest`; only tag releases that have passed the required release checks should be used for production. Check the build logs and package digest in GHCR. Set package visibility to **Public** if RunPod should pull anonymously.

The PAT in a local `.env` is not used by GitHub Actions. A maintainer with permission to push and dispatch workflows must push the workflow and code to the repository, then launch it. Publishing to the existing package requires the owner `acdevmedia` to grant the repository's workflow package write access.

## Optional local image build

```bash
docker build --build-arg LTX_VERSION=ltx-2.5 --build-arg CUDA_VERSION=12.8.0 -t ghcr.io/acdevmedia/ltx-studio:dev .
```

The image is Linux/amd64 and requires the NVIDIA container runtime when run. Building can work on a machine with no GPU. RunPod GPU runtime and model generation still need GPU validation.

## Manual GHCR publishing

The local fallback helper reads `GITHUB_PACKAGES_PAT` from the environment or ignored `.env` (key name exactly `GITHUB_PACKAGES_PAT`). Use a dated immutable release tag or semantic version. It tags the image with the release and current Git SHA, authenticates with `docker login --password-stdin`, and pushes with Buildx. It never passes the token to Docker build or stores it in the image.

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
