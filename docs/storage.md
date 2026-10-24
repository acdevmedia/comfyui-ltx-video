# Persistent storage and S3-compatible backup

ComfyUI's mutable tree is rooted at `/workspace/ComfyUI`. Model categories are under `models/`; input and output are persistent. The model provisioner never removes model files. Startup only copies packaged workflow files when the destination filename is absent.

## Configuration and precedence

Backup activates only when `REALTIME_BACKUP=true`. Set `S3_BUCKET`, credentials, and `AWS_DEFAULT_REGION`. For custom endpoints set `S3_ENDPOINT_URL`; MinIO commonly uses `S3_FORCE_PATH_STYLE=true`. For DigitalOcean, either set generic variables (`S3_BUCKET`, `S3_ENDPOINT_URL`, `AWS_DEFAULT_REGION`, access keys) or the legacy `SPACES_BUCKET`/`SPACES_REGION` aliases. If both forms are set, generic S3 values win. When only `SPACES_REGION` is supplied, the endpoint is built as `https://<region>.digitaloceanspaces.com` and that region is used to sign requests.

AWS standard credential resolution is supported by boto3, including environment credentials, role/web identity, or a profile. A custom endpoint requires access-key credentials. Credentials are never written into config files by the container.

Set `S3_PREFIX`, default `ltx25-studio`. Keys are `<prefix>/<persistent-instance-id>/<video|audio|metadata>/<source-relative-path>`. MP4, WAV, FLAC, MP3, M4A, and JSON output files are eligible. Files are checked for stable size and modification time before upload. Watch events and periodic reconciliation retry missed/failed uploads. The persistent state file avoids repeated transfers after restart. No S3 delete or sync-delete operation is used.

## Commands

Inside the container:

```bash
/opt/ltx25-studio/backup/cloud-backup.sh
/opt/ltx25-studio/backup/verify-backup.sh
tail -f /workspace/logs/backup.log
```

The one-shot command uses a fresh run ID and copies eligible outputs without deleting anything. Verification writes a small test object and attempts to delete it; delete permission is optional. If deletion is denied, the command reports that the small test object remains. Normal backup requires PutObject and the credential provider's signing permissions; it does not list or delete objects.

If backup startup is misconfigured, the error is logged to `/workspace/logs/backup.log`; ComfyUI remains available. With `REALTIME_BACKUP` unset or false, the watcher does not start.

## Provider examples

AWS S3:

```dotenv
REALTIME_BACKUP=true
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET=my-bucket
S3_PREFIX=ltx25-studio
```

DigitalOcean Spaces (example region `nyc3`):

```dotenv
REALTIME_BACKUP=true
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=nyc3
S3_BUCKET=my-space
S3_ENDPOINT_URL=https://nyc3.digitaloceanspaces.com
S3_PREFIX=ltx25-studio
```

MinIO:

```dotenv
REALTIME_BACKUP=true
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET=ltx-output
S3_ENDPOINT_URL=https://minio.example.net
S3_FORCE_PATH_STYLE=true
```

Set `BACKUP_SETTLE_SECONDS` for the quiet period before transfer and `BACKUP_RECHECK_SECONDS` for reconciliation cadence. `BACKUP_SOURCE_DIR` defaults to `/workspace/ComfyUI/output`.
