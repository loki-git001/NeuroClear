import asyncio
import logging
import os
import shutil
import tempfile
import time

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# NeuroClear pipeline modules
from services.whisper_service import transcribe_audio_file
from services.alignment_service import align_audio_to_text
from services.slicer_service import slice_audio_by_words
from services.scoring_service import (
    calculate_prosody_metrics,
    detect_stutters,
    detect_false_starts,
)
from services.llm_service import generate_clinical_report
from services.cancellation import CancellationToken

# ── Logging ──────────────────────────────────────────────────────────────────
logger = logging.getLogger("neuroclear")

# ── Constants ────────────────────────────────────────────────────────────────
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB — a 60-second clinical recording

ALLOWED_AUDIO_TYPES = {
    "audio/wav", "audio/x-wav", "audio/wave",
    "audio/mpeg", "audio/mp3",
    "audio/ogg", "audio/webm",
    "audio/flac", "audio/x-flac",
}

# ── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="NeuroClear API",
    description="Automated Speech Pathology & Dysarthria Screening API",
    version="1.0.0",
)

# ── Rate Limiting ────────────────────────────────────────────────────────────
# Limits incoming requests by the client's IP address
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


class PipelineTimingMiddleware(BaseHTTPMiddleware):
    """Measure total end-to-end request latency and expose it as a response header.

    The header ``X-Pipeline-Latency-Ms`` is added to every response and
    contains the elapsed wall-clock time in milliseconds (3 decimal places)
    from the moment FastAPI begins processing the request until the response
    is fully assembled.  This covers the full ML pipeline execution time:
    Whisper inference, Wav2Vec2 alignment, DSP scoring, and the Gemini API call.
    """

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()          # Monotonic, sub-microsecond resolution
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1_000
        response.headers["X-Pipeline-Latency-Ms"] = f"{elapsed_ms:.3f}"
        return response


# ── Middleware stack (order matters — last added = outermost wrapper) ─────────
# 1. Timing middleware must be added FIRST so it wraps the entire request,
#    including all other middleware and the route handler itself.
app.add_middleware(PipelineTimingMiddleware)

# 2. CORS middleware runs inside the timing wrapper.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _cleanup_file(path: str) -> None:
    """Remove a temporary file from disk. Safe to call from BackgroundTasks."""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError as err:
        logger.warning("Failed to remove temp file %s: %s", path, err)


def _cleanup_dir(path: str) -> None:
    """Recursively remove a temporary directory. Prevents disk exhaustion."""
    try:
        if path and os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
    except OSError as err:
        logger.warning("Failed to remove temp dir %s: %s", path, err)


def _start_disconnect_monitor(request: Request, token: CancellationToken) -> None:
    """Spins up an async task on the main event loop to watch for client disconnects."""
    async def _watch():
        while not token.is_cancelled:
            if await request.is_disconnected():
                logger.warning("Client disconnected. Triggering pipeline cancellation.")
                token.cancel()
                return
            await asyncio.sleep(0.5)  # Poll every 500ms

    try:
        loop = asyncio.get_running_loop()
        asyncio.run_coroutine_threadsafe(_watch(), loop)
    except Exception as e:
        logger.error("Could not start disconnect monitor: %s", e)


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Health check endpoint to verify backend service availability."""
    return {"status": "online", "service": "NeuroClear API"}


@app.post("/analyze")
@limiter.limit("5/minute")  # Restrict to 5 uploads per minute per IP
def analyze_speech(
    request: Request,
    background_tasks: BackgroundTasks,
    audio_file: UploadFile = File(...),
    target_text: str = Form(...),
):
    """
    Accepts an audio file upload and a target reference text.
    Runs the 5-stage NeuroClear pipeline and returns a structured clinical report.
    """
    tmp_path = ""
    sliced_dir = ""  # Track the sliced audio directory for guaranteed cleanup
    try:
        # ── Input validation ─────────────────────────────────────────────
        content_type = (audio_file.content_type or "").lower()
        if content_type not in ALLOWED_AUDIO_TYPES:
            raise HTTPException(
                status_code=415,
                detail=(
                    f"Unsupported media type '{content_type}'. "
                    "Please upload an audio file (WAV, MP3, OGG, WebM, or FLAC)."
                ),
            )

        # ── File size enforcement (prevents disk exhaustion attacks) ─────
        file_bytes = audio_file.file.read()
        if len(file_bytes) > MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"File too large ({len(file_bytes) / (1024*1024):.1f} MB). "
                    f"Maximum allowed size is {MAX_UPLOAD_SIZE / (1024*1024):.0f} MB."
                ),
            )

        # ── Setup Cancellation Monitor ───────────────────────────────────
        token = CancellationToken()
        _start_disconnect_monitor(request, token)

        # ── Write validated bytes to a temp file ─────────────────────────
        suffix = os.path.splitext(audio_file.filename or "")[1] or ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir="/tmp") as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        # ── Stage 1: Whisper ASR ─────────────────────────────────────────
        if token.is_cancelled:
            raise HTTPException(status_code=499, detail="Client Disconnected")
        whisper_result = transcribe_audio_file(tmp_path)
        whisper_text = whisper_result.get("text", "")

        # ── Stage 2: Forced Alignment ────────────────────────────────────
        if token.is_cancelled:
            raise HTTPException(status_code=499, detail="Client Disconnected")
        alignments = align_audio_to_text(tmp_path, target_text)
        if not alignments:
            raise HTTPException(
                status_code=400,
                detail="Forced alignment failed. Verify audio file contains clear speech.",
            )

        # ── Stage 3: Audio Slicing ───────────────────────────────────────
        if token.is_cancelled:
            raise HTTPException(status_code=499, detail="Client Disconnected")
        # Use /app/data as the output root (owned by appuser in Docker)
        source_stem = os.path.splitext(os.path.basename(tmp_path))[0]
        sliced_dir = os.path.join("data", "sliced", source_stem)
        slices = slice_audio_by_words(
            tmp_path, alignments, output_dir=sliced_dir, sample_rate=16000
        )

        # ── Stage 4: Clinical Scoring Metrics ────────────────────────────
        if token.is_cancelled:
            raise HTTPException(status_code=499, detail="Client Disconnected")
        total_audio_duration = alignments[-1]["end"] if alignments else 0.0
        false_starts = detect_false_starts(tmp_path, alignments)
        prosody = calculate_prosody_metrics(alignments, total_audio_duration, false_starts)
        stutter_results = detect_stutters(slices)

        # ── Stage 5: Gemini LLM Clinical Report ─────────────────────────
        # CRITICAL CHECKPOINT: Ensure we don't make an expensive LLM network call 
        # if the client has already dropped the connection.
        if token.is_cancelled:
            raise HTTPException(status_code=499, detail="Client Disconnected")
            
        clinical_report = generate_clinical_report(
            target_text=target_text,
            patient_text=whisper_text,
            prosody_data=prosody,
            articulation_data=alignments,
            tremor_data=stutter_results,
            false_start_data=false_starts,
            cancellation_token=token,
        )

        return clinical_report

    except HTTPException:
        # Re-raise client errors (400, 415) without wrapping them
        raise

    except Exception as err:
        logger.error("Pipeline failed: %s", err, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred during analysis. Please try again.",
        )

    finally:
        # ── GUARANTEED CLEANUP — runs on success, error, or cancellation ──
        _cleanup_file(tmp_path)
        _cleanup_dir(sliced_dir)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)