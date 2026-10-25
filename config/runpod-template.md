# RunPod template: LTX 2.5 Distilled ComfyUI Video One-Click

## Quick start

1. Create a Hugging Face account at [huggingface.co/join](https://huggingface.co/join), or sign in to your existing account.
2. Create a **Read** access token at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens). Copy it and keep it private.
3. While signed into that same Hugging Face account, open each required repository and accept its access terms: [Lightricks/LTX-2.5](https://huggingface.co/Lightricks/LTX-2.5), [Comfy-Org/gemma-4](https://huggingface.co/Comfy-Org/gemma-4), and [Lightricks/LTX-2.5-22b-IC-LoRA-Ingredients](https://huggingface.co/Lightricks/LTX-2.5-22b-IC-LoRA-Ingredients). Access approval is separate for each repository.
4. In RunPod, open **Settings → Secrets**, create a secret named exactly `HUGGINGFACE_TOKEN`, and paste the Hugging Face token as its value. The template passes it to the model downloader automatically. Do not put the token in a public template field.
5. Create a Pod from **LTX 2.5 Distilled ComfyUI Video One-Click**. Keep the container disk at its **200 GB default**. If you change it, use **at least 150 GB**. Choose an NVIDIA GPU; A100 80 GB is recommended.
6. On first launch, wait for model downloads to finish and for the Pod logs to say ComfyUI is ready. Then open **Connect → HTTP service 8188 / ComfyUI**.

The first launch downloads about **43 GiB** of models (about 108 GiB with `AUTO_DOWNLOAD_ADAPTERS=true` for Ingredients). If logs say a repository is gated, accept access to that exact repository using the account associated with the token. If they say the token is missing, verify the RunPod Secret name is `HUGGINGFACE_TOKEN`.

**Storage is temporary:** this template has no persistent volume. Download outputs before stopping or replacing the Pod, or set up optional S3 backup.

## Template settings

| Setting | Value |
|---|---|
| Container image | `ghcr.io/acdevmedia/ltx-studio:2.5` |
| GPU | NVIDIA; A100 80 GB recommended |
| Container disk | 200 GB default; 150 GB minimum recommended |
| Persistent volume | None |
| Start command | Empty |
| Registry credentials | None |
| Exposed application port | HTTP 8188 (ComfyUI) |
| RunPod Web terminal | Available from the Pod Connect tab; no application port required |

The template exposes only HTTP 8188 for ComfyUI. RunPod provides its browser-based Web terminal in the Pod Connect tab; it does not need an exposed container port. JupyterLab, SSH, and the legacy file/proxy ports are not exposed by this template. The template payload lists its environment fields in alphabetical order. Hugging Face and optional S3 credentials are passed through RunPod Secrets. No manual login, installation script, model download, workflow import, or ComfyUI restart is needed.

## Storage estimate

The original INT8 ConvRot filmmaker workflow uses about 43.18 GiB. Ingredients adds about 64.81 GiB when `AUTO_DOWNLOAD_ADAPTERS=true`, for about 107.99 GiB before temporary download/cache overhead. The optional BF16 prompt-enhancement encoder adds 9.57 GiB. The 200 GB default leaves room for downloads and generated files; do not reduce the container disk below 150 GB. The README has the per-file size table.

## Optional S3 backup

The template defaults to DigitalOcean Spaces in SFO3. Create RunPod Secrets named `S3_ACCESS_KEY_ID` and `S3_SECRET_ACCESS_KEY`, set `S3_BUCKET`, then set `REALTIME_BACKUP=true`. Backup is off by default and does not block generation. See [storage setup](../docs/storage.md) for AWS, DigitalOcean Spaces, and MinIO.

This standard template does not expose Jupyter, SSH, or the legacy file-manager service. See [deployment](../docs/deployment.md) for release and template maintenance.
