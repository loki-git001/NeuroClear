# ── Stage: Runtime ────────────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# ── System dependencies ───────────────────────────────────────────────────────
# ffmpeg   : required by pydub to decode .webm audio from the browser
# libsndfile1 : required by soundfile/librosa to load audio arrays in Python
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ───────────────────────────────────────────────────────
# Use Astral's 'uv' for massively faster dependency resolution and installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

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