# Video and audio output browser

This ComfyUI frontend extension reads the recent `/history` response and renders real HTML5 video/audio players using ComfyUI's `/view` endpoint. It updates after a queued graph finishes, supports nested output folders, and exposes the original file for download. It requests at most the latest 100 history entries when opened; it does not scan output files or poll while closed.

The pinned frontend build must be checked on a RunPod GPU pod before release. ComfyUI's `SaveVideo` output node also renders its own video preview in the graph.
