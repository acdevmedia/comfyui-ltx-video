# RunPod template: LTX 2.5 Distilled ComfyUI Video One-Click

## Template settings

| Setting | Value |
|---|---|
| Container image | `ghcr.io/acdevmedia/ltx-studio:2.5` |
| GPU | NVIDIA; A100 80 GB recommended |
| Container disk | 200 GB |
| Persistent volume | None |
| Start command | Empty |
| Registry credentials | None |
| HTTP ports | 8188, 8888, 8675 |
| TCP ports | 22, 8080 |
| UDP ports | 22, 8080 |

These ports match the original ComfyUI template. HTTP 8188 serves ComfyUI. HTTP 8888 is available if Jupyter is enabled. No persistent storage is configured: container files, models, cache, logs, and generated outputs can be lost when the Pod is stopped or replaced. Download outputs or configure S3 backup for durable copies.

**Storage requirement:** The original INT8 ConvRot filmmaker workflow plus the required Ingredients BF16 weights total about 108 GiB, before the 2 GiB downloader headroom. The 200 GB container disk leaves working room for temporary cache and generated files. No persistent volume is allocated.

## Environment variables

The checked-in template payload in `config/runpod-template.json` lists all environment keys in ascending alphabetical order. Add sensitive values through RunPod Secrets. Do not use registry credentials or a template start-command override.

For gated model downloads, create a RunPod Secret named `HUGGINGFACE_TOKEN` with an account token that has accepted the LTX-2.5 model terms. The template references it as `{{ RUNPOD_SECRET_HUGGINGFACE_TOKEN }}` for the `HF_TOKEN` variable. `HUGGING_FACE_HUB_TOKEN` is left empty as an optional alternate token name; `HF_TOKEN` takes precedence.

The S3 fields default to DigitalOcean Spaces in SFO3:

- `S3_ENDPOINT_URL=https://sfo3.digitaloceanspaces.com`
- `S3_REGION=sfo3`
- `S3_PREFIX=ltx25-studio`
- `S3_STORAGE_CLASS=STANDARD`
- `S3_SSE=none`
- `REALTIME_BACKUP=false`

Create RunPod Secrets named `S3_ACCESS_KEY_ID` and `S3_SECRET_ACCESS_KEY`, set `S3_BUCKET`, then set `REALTIME_BACKUP=true` to enable real-time backup. The template references credential secrets with `{{ RUNPOD_SECRET_S3_ACCESS_KEY_ID }}` and `{{ RUNPOD_SECRET_S3_SECRET_ACCESS_KEY }}`. All exposed backup configuration uses `S3_*` names, including for AWS S3. See [storage setup](../docs/storage.md) for AWS, DigitalOcean Spaces, and MinIO examples.

Jupyter is disabled by default. To enable it, set `ENABLE_JUPYTER=true` and create a RunPod Secret named `JUPYTER_TOKEN`. The optional SSH public key uses `PUBLIC_KEY`. `AI_TOOLKIT_AUTH` is also populated through a RunPod Secret.

## Create or update the RunPod template

Publish `ghcr.io/acdevmedia/ltx-studio:2.5` first and verify that it can be pulled anonymously. The script reads `RUNPOD_API_KEY` from the environment or ignored `.env`. It refuses to publish a template if the exact image tag is not publicly pullable, and avoids duplicates unless `--update-existing` is supplied.

```bash
python3 scripts/create-runpod-template.py --dry-run
python3 scripts/create-runpod-template.py --image ghcr.io/acdevmedia/ltx-studio:2.5 --update-existing
```

The template payload and the RunPod API update use no persistent volume, an empty start command, the port lists above, and no registry credentials. Set HF and optional S3 secrets in the RunPod UI after updating the template. See [deployment](../docs/deployment.md) for release validation.
