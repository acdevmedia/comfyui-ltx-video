# S3-compatible output backup

This RunPod template uses container storage only. `/workspace/ComfyUI/output` is available during the Pod's lifetime, but files may be lost when the Pod is stopped or replaced. Enable S3 backup or download important files to keep them.

## Configuration

Backup activates only when `REALTIME_BACKUP=true` and the destination and credentials are configured. All provider settings use the `S3_*` environment prefix; AWS-named variables are not part of the template contract.

| Variable | Default | Purpose |
|---|---|---|
| `REALTIME_BACKUP` | `false` | Enable the non-deleting background watcher. |
| `S3_ACCESS_KEY_ID` | empty | S3-compatible access key. |
| `S3_BUCKET` | empty | Destination bucket or Space. |
| `S3_ENDPOINT_URL` | `https://sfo3.digitaloceanspaces.com` | Provider endpoint. |
| `S3_FORCE_PATH_STYLE` | `false` | Set `true` for MinIO endpoints that require path-style requests. |
| `S3_PREFIX` | `ltx25-studio` | Destination key prefix. |
| `S3_REGION` | `sfo3` | Provider signing region. |
| `S3_SECRET_ACCESS_KEY` | empty | S3-compatible secret key. |
| `S3_SESSION_TOKEN` | empty | Optional temporary credential token. |
| `S3_SSE` | `none` | Optional server-side encryption setting. |
| `S3_STORAGE_CLASS` | `STANDARD` | Optional storage class. |
| `BACKUP_SOURCE_DIR` | `/workspace/ComfyUI/output` | Output tree to monitor. |
| `BACKUP_RECHECK_SECONDS` | `120` | Periodic reconciliation interval. |
| `BACKUP_SETTLE_SECONDS` | `8` | Quiet period before upload. |

The RunPod template defaults to DigitalOcean Spaces SFO3. Set the bucket and access keys and mark credentials as RunPod Secrets. To use another provider, set its region and endpoint. Credentials are passed directly to the client and are never written to configuration files or logs.

Eligible completed MP4, WAV, FLAC, MP3, M4A, and JSON outputs are monitored recursively. The watcher waits for stable size and modification time before upload, retries failures, and periodically reconciles missed events. Object keys include the prefix, persistent instance identifier, media type, and source-relative path. No remote delete or sync-delete operation is used. Backup errors are logged while ComfyUI remains available.

## Commands

Inside the container:

```bash
/opt/ltx25-studio/backup/cloud-backup.sh
/opt/ltx25-studio/backup/verify-backup.sh
tail -f /workspace/logs/backup.log
```

The one-shot command uploads eligible files without deleting local files or remote objects. Verification attempts a small test upload and removes that test object when the provider permits; deletion permission is not required for normal backups.

## Provider examples

Amazon S3:

```dotenv
REALTIME_BACKUP=true
S3_ACCESS_KEY_ID=...
S3_SECRET_ACCESS_KEY=...
S3_REGION=us-east-1
S3_BUCKET=my-bucket
S3_ENDPOINT_URL=https://s3.us-east-1.amazonaws.com
S3_PREFIX=ltx25-studio
S3_STORAGE_CLASS=STANDARD
S3_SSE=AES256
```

DigitalOcean Spaces SFO3:

```dotenv
REALTIME_BACKUP=true
S3_ACCESS_KEY_ID=...
S3_SECRET_ACCESS_KEY=...
S3_REGION=sfo3
S3_BUCKET=my-space
S3_ENDPOINT_URL=https://sfo3.digitaloceanspaces.com
S3_PREFIX=ltx25-studio
S3_STORAGE_CLASS=STANDARD
S3_SSE=none
```

MinIO:

```dotenv
REALTIME_BACKUP=true
S3_ACCESS_KEY_ID=...
S3_SECRET_ACCESS_KEY=...
S3_REGION=us-east-1
S3_BUCKET=ltx-output
S3_ENDPOINT_URL=https://minio.example.net
S3_FORCE_PATH_STYLE=true
S3_PREFIX=ltx25-studio
```

The SFO3 values in the RunPod template are defaults, not mandatory; replace them for AWS or MinIO. Configure all values in the RunPod environment-variable/secret interface. The local `.env.example` is a reference only.
