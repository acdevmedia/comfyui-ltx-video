# RunPod template: LTX 2.5 Distilled Video and one click

## Template settings

| Setting | Value |
|---|---|
| Container image | `ghcr.io/acdevmedia/ltx-studio:2.5` |
| GPU | NVIDIA; A100 80 GB recommended |
| Container disk | 100 GB |
| Persistent volume | None |
| Start command | Empty |
| Registry credentials | None |
| HTTP ports | 8188, 8888, 8675 |
| TCP ports | 22, 8080 |
| UDP ports | 22, 8080 |

These ports match the original ComfyUI template. HTTP 8188 serves ComfyUI. HTTP 8888 is available if Jupyter is enabled. No persistent storage is configured: container files, models, cache, logs, and generated outputs can be lost when the Pod is stopped or replaced. Download outputs or configure S3 backup for durable copies.

## Environment variables

The checked-in template payload in `config/runpod-template.json` lists all environment keys in ascending alphabetical order. Add sensitive values through RunPod Secrets. Do not use registry credentials or a template start-command override.

For gated model downloads, supply `HF_TOKEN` with an account that has accepted the LTX-2.5 model terms. `HUGGING_FACE_HUB_TOKEN` is an alternate token name; `HF_TOKEN` takes precedence.

The S3 fields default to DigitalOcean Spaces in SFO3:

- `S3_ENDPOINT_URL=https://sfo3.digitaloceanspaces.com`
- `S3_REGION=sfo3`
- `S3_PREFIX=ltx25-studio`
- `S3_STORAGE_CLASS=STANDARD`
- `S3_SSE=none`
- `REALTIME_BACKUP=false`

Set `S3_BUCKET`, `S3_ACCESS_KEY_ID`, and `S3_SECRET_ACCESS_KEY`, then set `REALTIME_BACKUP=true` to enable real-time backup. All exposed backup configuration uses `S3_*` names, including for AWS S3. See [storage setup](../docs/storage.md) for AWS, DigitalOcean Spaces, and MinIO examples.

Jupyter is disabled by default. To enable it, set `ENABLE_JUPYTER=true` and a private `JUPYTER_TOKEN`. The optional SSH public key uses `PUBLIC_KEY`.

## Create or update the RunPod template

Publish `ghcr.io/acdevmedia/ltx-studio:2.5` first and verify that it can be pulled anonymously. The script reads `RUNPOD_API_KEY` from the environment or ignored `.env`. It refuses to publish a template if the exact image tag is not publicly pullable, and avoids duplicates unless `--update-existing` is supplied.

```bash
python3 scripts/create-runpod-template.py --dry-run
python3 scripts/create-runpod-template.py --image ghcr.io/acdevmedia/ltx-studio:2.5 --update-existing
```

The template payload and the RunPod API update use no persistent volume, an empty start command, the port lists above, and no registry credentials. Set HF and optional S3 secrets in the RunPod UI after updating the template. See [deployment](../docs/deployment.md) for release validation.
