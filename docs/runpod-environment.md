# Runpod template environment

Synced from account template **LTX 2.5 Distilled ComfyUI Video One-Click** (`abmsxu1p5j`) on 2026-10-30.

[Open template](https://console.runpod.io/deploy?template=abmsxu1p5j)

Image: `ghcr.io/acdevmedia/ltx-studio:2.5`. Container disk: **200 GB**. Workspace: `/workspace`. Template service: `8188/http`. No persistent volume is requested by the repository template configuration.

`config/runpod-template.json` holds the Pod defaults. `.runpod/template-source.json` records the account source. `.runpod/hub.json` exposes the same values through Hub inputs or fixed values. `.runpod/tests.json` uses the same defaults for readiness tests.

## Credentials

Create Runpod Secret `HUGGINGFACE_TOKEN` with a Hugging Face read token and accept the gated model terms. Secret references are passed through unchanged; no credential values are stored here. Optional S3 credentials are only needed when backup is enabled.

## Template variables

### `AUTO_DOWNLOAD_ADAPTERS`

Default: `false`.

Download the optional Ingredients BF16 models and IC-LoRA at startup; adds about 65 GiB.

### `AUTO_DOWNLOAD_MODELS`

Default: `true`.

Download missing required model files at startup. If disabled, all required weights must already exist on disk.

### `BACKUP_RECHECK_SECONDS`

Default: `120`.

Seconds between backup reconciliation scans; runtime enforces a minimum of 10.

### `BACKUP_SETTLE_SECONDS`

Default: `8`.

Seconds to wait for output files to settle before upload.

### `BACKUP_SOURCE_DIR`

Default: `/workspace/ComfyUI/output`.

Local output directory watched by S3 backup.

### `COMFYUI_PORT`

Default: `8188`.

Internal ComfyUI port. Keep 8188: the Hub gateway targets this port.

### `HF_HOME`

Default: `/workspace/.cache/huggingface`.

Hugging Face cache directory on container storage.

### `HF_TOKEN`

Default: `{{ RUNPOD_SECRET_HUGGINGFACE_TOKEN }}`.

Hugging Face read token supplied through the Runpod Secret HUGGINGFACE_TOKEN. Accept gated model terms before deployment.

### `HUGGING_FACE_HUB_TOKEN`

Default: `{{ RUNPOD_SECRET_HUGGINGFACE_TOKEN }}`.

Compatibility alias for the same HUGGINGFACE_TOKEN secret used by HF_TOKEN.

### `LOG_LEVEL`

Default: `INFO`.

Template log-level setting. Current startup scripts do not read it; retained for template parity.

### `LTX_DEFAULT_ASPECT_RATIO`

Default: `16:9`.

Aspect ratio seeded into newly installed workflows: 16:9, 9:16, 4:3, 1:1, or 21:9.

### `LTX_DEFAULT_DURATION`

Default: `30`.

Requested duration in seconds for newly installed workflows; long clips require sufficient GPU memory.

### `LTX_DEFAULT_FPS`

Default: `24`.

Frames per second seeded into newly installed workflows.

### `LTX_DEFAULT_MEGAPIXELS`

Default: `0.5`.

Resolution target for newly installed workflows; the installer clamps dimensions to a 0.2–2.0 megapixel range.

### `LTX_DEFAULT_WORKFLOW`

Default: `01_LTX25_Image_to_Video`.

Packaged workflow filename without .json to open by default. Existing workflow files are preserved.

### `LTX_MODEL_VARIANT`

Default: `int8-convrot`.

Template model-variant label. Downloads are selected by the version model manifest; changing this label alone does not switch precision.

### `LTX_VERSION`

Default: `ltx-2.5`.

Baked version profile. Keep ltx-2.5 unless rebuilding the image with another packaged profile.

### `REALTIME_BACKUP`

Default: `false`.

Enable automatic S3-compatible output backup. Configure a bucket and both credentials before enabling.

### `S3_ACCESS_KEY_ID`

Default: `{{ RUNPOD_SECRET_S3_ACCESS_KEY_ID }}`.

S3 access key supplied by Runpod Secret S3_ACCESS_KEY_ID; used only for optional backup.

### `S3_BUCKET`

Default: `YOUR_BUCKET`.

Destination bucket name. Replace YOUR_BUCKET before enabling backup.

### `S3_ENDPOINT_URL`

Default: `https://sfo3.digitaloceanspaces.com`.

S3 API endpoint. Template defaults to DigitalOcean Spaces SFO3; use the endpoint for your storage provider.

### `S3_FORCE_PATH_STYLE`

Default: `false`.

Use path-style S3 bucket addressing when required by the storage provider.

### `S3_PREFIX`

Default: `ltx25-studio`.

Object-key prefix under the destination bucket.

### `S3_REGION`

Default: `sfo3`.

S3 region used to sign requests.

### `S3_SECRET_ACCESS_KEY`

Default: `{{ RUNPOD_SECRET_S3_SECRET_ACCESS_KEY }}`.

S3 secret key supplied by Runpod Secret S3_SECRET_ACCESS_KEY; used only for optional backup.

### `S3_SESSION_TOKEN`

Default: `OPTIONAL_TEMPORARY_TOKEN`.

Optional temporary S3 session token. Replace OPTIONAL_TEMPORARY_TOKEN with a Runpod Secret reference when using temporary credentials; placeholder means no token.

### `S3_SSE`

Default: `none`.

Server-side encryption setting: none disables it; use AES256 or aws:kms:<key-id> as supported by your provider.

### `S3_STORAGE_CLASS`

Default: `STANDARD`.

Storage class passed to S3 uploads; STANDARD is the template default.

### `TINI_SUBREAPER`

Default: `1`.

Enable Tini subreaper behavior in the original container entrypoint.

## Hub additions and differences

The Pod template uses the root image and HTTP 8188. The Hub builds `.runpod/Dockerfile`, retaining ComfyUI internally on 8188 and exposing its gateway on HTTP 8000. Readiness uses HTTP 8001. The original Pod template keeps its existing image and ports.

- `PORT=8000`: Hub gateway HTTP/WebSocket port. This is separate from the template ComfyUI port 8188.
- `PORT_HEALTH=8001`: Hub readiness port; /ping returns 503 until ComfyUI is ready.
- `COMFYUI_ATTENTION=sage`: an explicit Hub input for the existing image default; absent from the account Pod template.

Template defaults are preserved, including optional placeholders. Update optional settings before enabling their feature. Workflow defaults apply to newly installed workflow files; existing user edits are preserved. A Serverless browser session requires a single active worker and authenticated HTTP/WebSocket access as described in `.runpod/README.md`.

## Account template metadata

Visibility: public. No custom entrypoint or start command is set in the account template.

The account API leaves `startJupyter` and `startSsh` unset. Its explicit service ports list only `8188/http`.
