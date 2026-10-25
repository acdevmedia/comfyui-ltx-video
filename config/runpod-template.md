# RunPod template: ACDEV LTX-2.5 Studio

## Template fields

| Field | Value |
|---|---|
| Name | ACDEV LTX-2.5 Studio |
| Container image | `ghcr.io/acdevmedia/ltx-studio:2.5` (use the digest recorded after publishing for a fixed release) |
| GPU | A100 80GB recommended |
| Container disk | 100 GB (matches the working ValyrianTech template and leaves room for CUDA/PyTorch application layers) |
| Persistent volume | Mount at `/workspace`; 200 GB minimum, 250 GB preferred |
| HTTP port | `8188` ComfyUI direct |
| HTTP port | `8080` nginx reverse proxy to ComfyUI and output files |
| HTTP port | `8888` only if `ENABLE_JUPYTER=true` and a Jupyter token is set |
| TCP port | `22` SSH; add `PUBLIC_KEY` if SSH is needed |

Do not add `8675` (the upstream port served its unrelated AI Toolkit UI) or other model-serving ports. HTTP `8080` retains the upstream nginx proxy. The image contains no model weights. First startup downloads the model manifest to persistent storage. Storage depends on which workflows and adapters are enabled; keep additional room for outputs.

## Environment variables

Add secrets using RunPod's environment/secret interface; never add secret values to template text or image build settings.

Required for first gated download:

- Replace the visible `HF_TOKEN` value `YOUR_HUGGING_FACE_TOKEN` with your Hugging Face token. Mark it as a secret in RunPod. `HUGGING_FACE_HUB_TOKEN` is also accepted if you prefer that name.

Defaults:

- `LTX_VERSION=ltx-2.5` (must match the profile baked into the selected image)
- `COMFYUI_PORT=8188`
- `LTX_MODEL_VARIANT=int8-convrot`
- `LTX_DEFAULT_WORKFLOW=01_LTX25_Image_to_Video`
- `LTX_DEFAULT_DURATION=30`
- `LTX_DEFAULT_FPS=24`
- `LTX_DEFAULT_MEGAPIXELS=0.5`
- `LTX_DEFAULT_ASPECT_RATIO=16:9`
- `AUTO_DOWNLOAD_MODELS=true`
- `AUTO_DOWNLOAD_ADAPTERS=true`
- `HF_HOME=/workspace/.cache/huggingface`
- `REALTIME_BACKUP=false`
- `BACKUP_SOURCE_DIR=/workspace/ComfyUI/output`
- `BACKUP_RECHECK_SECONDS=120`
- `BACKUP_SETTLE_SECONDS=8`

Optional backup: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AWS_DEFAULT_REGION`, `S3_BUCKET`, `S3_ENDPOINT_URL`, `S3_PREFIX`, `S3_FORCE_PATH_STYLE`, `S3_STORAGE_CLASS`, `S3_SSE`. DigitalOcean aliases: `SPACES_BUCKET`, `SPACES_REGION`, `SPACES_PREFIX`. Generic `S3_*` values take precedence.

Optional admin services: `ENABLE_JUPYTER=true` requires a nonempty `JUPYTER_TOKEN`; `PUBLIC_KEY` enables SSH authorized-key access.

## Publish the template

First publish a versioned GHCR image, set the package public, and verify pull access. The reviewed API body is `config/runpod-template.json`; `scripts/create-runpod-template.py` checks for public pull access and duplicate names, then creates the public template using `RUNPOD_API_KEY` from the shell or ignored `.env`.

```bash
python3 scripts/create-runpod-template.py --image ghcr.io/acdevmedia/ltx-studio:2.5
```

Add Hugging Face and S3 credentials through RunPod Secrets after creation. Launch a test pod on an A100 80GB with persistent storage. Confirm automatic model downloads, ComfyUI readiness, one short video/audio generation, the output browser, and backup verification. See `docs/deployment.md` for release checks.
