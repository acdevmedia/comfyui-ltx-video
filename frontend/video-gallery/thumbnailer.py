#!/usr/bin/env python3
"""Create browser posters for completed ComfyUI video outputs."""
from __future__ import annotations

import hashlib
import os
import subprocess
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

OUTPUT = Path(os.environ.get("THUMBNAIL_SOURCE_DIR", "/workspace/ComfyUI/output"))
THUMB_DIR = OUTPUT / ".ltx25-thumbnails"
SETTLE = max(2, int(os.environ.get("THUMBNAIL_SETTLE_SECONDS", "3")))
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".mkv"}


def poster_path(video: Path) -> Path:
    rel = video.relative_to(OUTPUT).as_posix()
    digest = hashlib.sha256(rel.encode()).hexdigest()
    return THUMB_DIR / f"{digest}.jpg"


def make_poster(path: Path) -> None:
    try:
        if path.suffix.lower() not in VIDEO_EXTENSIONS or not path.is_file():
            return
        rel = path.relative_to(OUTPUT)
        if not rel.parts or rel.parts[0] == THUMB_DIR.name:
            return
        target = poster_path(path)
        if target.exists() and target.stat().st_mtime >= path.stat().st_mtime:
            return
        size = path.stat().st_size
        time.sleep(SETTLE)
        if not path.exists() or path.stat().st_size != size or size == 0:
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(".jpg.tmp")
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", "1", "-i", str(path),
             "-frames:v", "1", "-vf", "scale=480:-2", "-q:v", "4", "-f", "image2", "-y", str(temp)],
            capture_output=True, text=True, timeout=90,
        )
        if result.returncode == 0 and temp.exists() and temp.stat().st_size:
            temp.replace(target)
        else:
            temp.unlink(missing_ok=True)
            if result.stderr:
                print(f"[thumbnailer] ffmpeg failed for {rel}: {result.stderr.strip()[-500:]}", flush=True)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"[thumbnailer] could not process {path}: {exc}", flush=True)


class Handler(FileSystemEventHandler):
    # ComfyUI writes videos in place, so creation fires on an empty file; wait for the writer to close it.
    def on_closed(self, event):
        if not event.is_directory:
            make_poster(Path(event.src_path))

    def on_moved(self, event):
        if not event.is_directory:
            make_poster(Path(event.dest_path))


def reconcile() -> None:
    for path in OUTPUT.rglob("*"):
        if THUMB_DIR in path.parents:
            continue
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
            make_poster(path)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    observer = Observer()
    observer.schedule(Handler(), str(OUTPUT), recursive=True)
    observer.start()
    print(f"[thumbnailer] watching {OUTPUT}", flush=True)
    try:
        reconcile()
        interval = max(60, int(os.environ.get("THUMBNAIL_RECHECK_SECONDS", "600")))
        while True:
            time.sleep(interval)
            reconcile()
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()


if __name__ == "__main__":
    main()
