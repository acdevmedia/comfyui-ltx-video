# ACDEV LTX-2.5 Studio, adapted from the ValyrianTech RunPod/CUDA layout.
# Model weights are provisioned to persistent /workspace storage at first boot.
ARG CUDA_VERSION=12.8.0
ARG LTX_VERSION=ltx-2.5
FROM nvidia/cuda:${CUDA_VERSION}-devel-ubuntu22.04 AS builder
ARG CUDA_VERSION
ARG LTX_VERSION
ENV DEBIAN_FRONTEND=noninteractive VENV_PATH=/opt/venv
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv python-is-python3 git git-lfs curl ca-certificates \
    build-essential pkg-config libcairo2-dev libsqlite3-dev && \
    rm -rf /var/lib/apt/lists/*
RUN python3 -m venv ${VENV_PATH}
ENV PATH="${VENV_PATH}/bin:${PATH}"
COPY versions /opt/ltx25-studio/versions
RUN python - <<'PY'
import json, os
from pathlib import Path
profile = json.loads((Path('/opt/ltx25-studio/versions') / os.environ['LTX_VERSION'] / 'profile.json').read_text())
runtime = profile['runtime']
assert runtime['cuda_version'] == os.environ['CUDA_VERSION'], 'CUDA_VERSION does not match the selected LTX profile'
PY
RUN pip install --no-cache-dir --upgrade pip && \
    python -c 'import json,os; from pathlib import Path; p=json.loads((Path("/opt/ltx25-studio/versions")/os.environ["LTX_VERSION"]/"profile.json").read_text())["runtime"]; print(p["torch_version"],p["torchvision_version"],p["torchaudio_version"])' >/tmp/torch-versions && \
    read TORCH_VERSION TORCHVISION_VERSION TORCHAUDIO_VERSION </tmp/torch-versions && \
    TORCH_INDEX_URL="$(python -c 'import json,os; from pathlib import Path; print(json.loads((Path("/opt/ltx25-studio/versions")/os.environ["LTX_VERSION"]/"profile.json").read_text())["runtime"]["torch_index_url"])')" && \
    pip install --no-cache-dir "torch==${TORCH_VERSION}" "torchvision==${TORCHVISION_VERSION}" "torchaudio==${TORCHAUDIO_VERSION}" \
      --index-url "${TORCH_INDEX_URL}"
RUN git clone https://github.com/comfyanonymous/ComfyUI.git /opt/ltx25-studio/ComfyUI && \
    cd /opt/ltx25-studio/ComfyUI && git checkout --detach "$(python -c 'import json,os; from pathlib import Path; print(json.loads((Path("/opt/ltx25-studio/versions")/os.environ["LTX_VERSION"]/"profile.json").read_text())["runtime"]["comfyui_commit"])')" && \
    python -c 'import re; from pathlib import Path; p=Path("requirements.txt"); p.write_text("\n".join(x for x in p.read_text().splitlines() if not re.match(r"^\s*(torch|torchvision|torchaudio)(?:[<>=!~;#\[]|$)", x, re.I))+"\n")' && \
    pip install --no-cache-dir -r requirements.txt && \
    mkdir -p custom_nodes && \
    git clone https://github.com/ltdrdata/ComfyUI-Manager.git custom_nodes/ComfyUI-Manager && \
    cd custom_nodes/ComfyUI-Manager && git checkout --detach "$(python -c 'import json,os; from pathlib import Path; print(json.loads((Path("/opt/ltx25-studio/versions")/os.environ["LTX_VERSION"]/"profile.json").read_text())["runtime"]["manager_commit"])')" && \
    cd /opt/ltx25-studio/ComfyUI/custom_nodes && \
    git clone https://github.com/pythongosssss/ComfyUI-Custom-Scripts.git ComfyUI-Custom-Scripts && \
    cd ComfyUI-Custom-Scripts && git checkout --detach "$(python -c 'import json,os; from pathlib import Path; print(json.loads((Path("/opt/ltx25-studio/versions")/os.environ["LTX_VERSION"]/"profile.json").read_text())["runtime"]["custom_scripts_commit"])')" && \
    if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi && \
    cd /opt/ltx25-studio/ComfyUI/custom_nodes && \
    git clone https://github.com/Lightricks/ComfyUI-LTXVideo.git ComfyUI-LTXVideo && \
    cd ComfyUI-LTXVideo && git checkout --detach "$(python -c 'import json,os; from pathlib import Path; print(json.loads((Path("/opt/ltx25-studio/versions")/os.environ["LTX_VERSION"]/"profile.json").read_text())["runtime"]["ltxvideo_commit"])')" && \
    pip install --no-cache-dir -r requirements.txt && \
    PACKAGE_PINS="$(python -c 'import json,os; from pathlib import Path; r=json.loads((Path("/opt/ltx25-studio/versions")/os.environ["LTX_VERSION"]/"profile.json").read_text())["runtime"]; print(" ".join(["comfy-aimdo=="+r["comfy_aimdo_version"],"comfy-kitchen=="+r["comfy_kitchen_version"],"av=="+r["av_version"],"huggingface_hub=="+r["huggingface_hub_version"],"transformers=="+r["transformers_version"],"boto3=="+r["boto3_version"],"watchdog=="+r["watchdog_version"],"jupyterlab=="+r["jupyterlab_version"]]))'" && \
    pip install --no-cache-dir ${PACKAGE_PINS} && pip check

FROM nvidia/cuda:${CUDA_VERSION}-runtime-ubuntu22.04 AS runtime
ARG LTX_VERSION
ENV DEBIAN_FRONTEND=noninteractive PATH="/opt/venv/bin:/usr/local/cuda/bin:${PATH}" SHELL=/bin/bash
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv python-is-python3 openssh-server openssh-client git git-lfs \
    curl ca-certificates vim nginx libgl1 libglib2.0-0 libsqlite3-0 ffmpeg inotify-tools \
    util-linux rsync tini && rm -rf /var/lib/apt/lists/*
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/ltx25-studio/ComfyUI /opt/ltx25-studio/ComfyUI
COPY config /opt/ltx25-studio/config
COPY versions /opt/ltx25-studio/versions
COPY frontend/video-gallery/ /opt/ltx25-studio/ComfyUI/web/extensions/ACDEV-LTX25-video-gallery/
COPY docker /opt/ltx25-studio/docker
COPY scripts /opt/ltx25-studio/scripts
COPY backup /opt/ltx25-studio/backup
COPY .env.example /opt/ltx25-studio/.env.example
RUN chmod +x /opt/ltx25-studio/docker/*.sh /opt/ltx25-studio/scripts/*.sh /opt/ltx25-studio/backup/*.sh && \
    mkdir -p /workspace /run/sshd && \
    rm -rf /opt/ltx25-studio/ComfyUI/models/* /opt/ltx25-studio/ComfyUI/input/* /opt/ltx25-studio/ComfyUI/output/*
WORKDIR /workspace
ENV COMFYUI_DIR=/workspace/ComfyUI HF_HOME=/workspace/.cache/huggingface \
    LTX_VERSION=${LTX_VERSION} \
    MODEL_MANIFEST=/opt/ltx25-studio/versions/${LTX_VERSION}/config/models.json \
    ADAPTER_MANIFEST=/opt/ltx25-studio/versions/${LTX_VERSION}/config/adapters.json \
    WORKFLOW_SOURCE_DIR=/opt/ltx25-studio/versions/${LTX_VERSION}/workflows \
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
EXPOSE 8188 8888 22
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 CMD ["/opt/ltx25-studio/docker/healthcheck.sh"]
ENTRYPOINT ["/usr/bin/tini", "--", "/opt/ltx25-studio/docker/entrypoint.sh"]
