# ── Stage: Runtime ────────────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# ── System dependencies ───────────────────────────────────────────────────────
# ffmpeg   : required by pydub to decode .webm audio from the browser
# libsndfile1 : required by soundfile/librosa to load audio arrays in Python
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies (Modern uv sync) ──────────────────────────────────────
# Use Astral's 'uv' for massively faster dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set uv to install packages directly into the system python instead of a venv
ENV UV_PROJECT_ENVIRONMENT="/usr/local"

COPY pyproject.toml ./

# ── Force CPU-only PyTorch for AWS Free Tier ──────────────────────────────────
# Rewrite the local pyproject.toml on-the-fly to use the CPU index instead of CUDA.
# This prevents downloading gigabytes of NVIDIA drivers onto the small AWS disk.
RUN sed -i 's/pytorch-cu130/pytorch-cpu/g' pyproject.toml && \
    sed -i 's|https://download.pytorch.org/whl/cu130|https://download.pytorch.org/whl/cpu|g' pyproject.toml

# --no-dev excludes heavy tools. We drop --frozen so uv generates a fresh CPU lockfile.
RUN uv sync --no-dev

# ── Backend source code ───────────────────────────────────────────────────────
# Copy ONLY the backend files. The frontend/ folder, .git/, .venv/, notebooks/,
# and node_modules (if any) are excluded via .dockerignore.
COPY main.py .
COPY services/ ./services/

# ── Pre-bake HuggingFace model weights into the image ─────────────────────────
# Without this, the model (~400MB) would download at request-time, causing a
# 60-120s freeze on the first user request in every new container instance.
RUN python -c "\
from transformers import Wav2Vec2Processor, Wav2Vec2ForCTC; \
print('[Docker] Pre-downloading Wav2Vec2 model weights...'); \
Wav2Vec2Processor.from_pretrained('facebook/wav2vec2-base-960h'); \
Wav2Vec2ForCTC.from_pretrained('facebook/wav2vec2-base-960h'); \
print('[Docker] Model weights baked into image successfully.')"

# ── Security: run as non-root user ───────────────────────────────────────────
# The app accepts arbitrary audio file uploads; never run that as root.
RUN useradd --create-home --shell /bin/bash appuser
USER appuser

# ── Runtime ───────────────────────────────────────────────────────────────────
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]