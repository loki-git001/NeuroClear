import logging
import os
import shutil
import tempfile
import time

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

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

# ── Logging ──────────────────────────────────────────────────────────────────
logger = logging.getLogger("neuroclear")

# ── Constants ────────────────────────────────────────────────────────────────
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


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """Health check endpoint to verify backend service availability."""
    return {"status": "online", "service": "NeuroClear API"}


@app.post("/analyze")
def analyze_speech(
    background_tasks: BackgroundTasks,
    audio_file: UploadFile = File(...),
    target_text: str = Form(...),
):
    """
    Accepts an audio file upload and a target reference text.
    Runs the 5-stage NeuroClear pipeline and returns a structured clinical report.
    """
    tmp_path = ""
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

        # ── Chunked disk streaming (prevents OOM on large uploads) ───────
        suffix = os.path.splitext(audio_file.filename or "")[1] or ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(audio_file.file, tmp)
            tmp_path = tmp.name

        # ── Stage 1: Whisper ASR ─────────────────────────────────────────
        whisper_result = transcribe_audio_file(tmp_path)
        whisper_text = whisper_result.get("text", "")

        # ── Stage 2: Forced Alignment ────────────────────────────────────
        alignments = align_audio_to_text(tmp_path, target_text)
        if not alignments:
            raise HTTPException(
                status_code=400,
                detail="Forced alignment failed. Verify audio file contains clear speech.",
            )

        # ── Stage 3: Audio Slicing ───────────────────────────────────────
        slices = slice_audio_by_words(tmp_path, alignments, sample_rate=16000)

        # ── Stage 4: Clinical Scoring Metrics ────────────────────────────
        total_audio_duration = alignments[-1]["end"] if alignments else 0.0
        false_starts = detect_false_starts(tmp_path, alignments)
        prosody = calculate_prosody_metrics(alignments, total_audio_duration, false_starts)
        stutter_results = detect_stutters(slices)

        # ── Stage 5: Gemini LLM Clinical Report ─────────────────────────
        clinical_report = generate_clinical_report(
            target_text=target_text,
            patient_text=whisper_text,
            prosody_data=prosody,
            articulation_data=alignments,
            tremor_data=stutter_results,
            false_start_data=false_starts,
        )

        # Schedule temp file cleanup AFTER the response is sent
        background_tasks.add_task(_cleanup_file, tmp_path)

        return clinical_report

    except HTTPException:
        # Re-raise client errors (400, 415) without wrapping them
        _cleanup_file(tmp_path)
        raise

    except Exception as err:
        _cleanup_file(tmp_path)
        logger.error("Pipeline failed: %s", err, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred during analysis. Please try again.",
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)