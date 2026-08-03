# services/alignment_service.py
# ──────────────────────────────────────────────────────────────────────────────
# Stage 2 — Forced Alignment Service
#
# Uses WAV2VEC2_ASR_BASE_960H to produce CTC frame-level emissions, then
# torchaudio.functional.forced_align to map each character of the transcript
# to an exact time range.  Character-level alignments are merged back into
# word-level boundaries and returned as a structured list of dicts.
# ──────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import re
import time
from typing import List, Dict

import torch
import torchaudio

# ── Device Detection ─────────────────────────────────────────────────────────
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ── Model & Label Loading (runs once at import time) ─────────────────────────
_PIPELINE = torchaudio.pipelines.WAV2VEC2_ASR_BASE_960H

# Expected sample rate for the Wav2Vec2 model (16 kHz).
MODEL_SAMPLE_RATE: int = _PIPELINE.sample_rate  # 16_000

# Build the acoustic model and move it to the selected device.
print(f"[alignment_service] Loading WAV2VEC2_ASR_BASE_960H on '{DEVICE}' …")
_MODEL = _PIPELINE.get_model().to(DEVICE)
_MODEL.eval()

# Build a character → token-ID mapping from the pipeline's label list.
# Labels are ordered so that index 0 = CTC blank, 1 = <space> ("|"), 2..27 = A..Z, etc.
_LABELS: list[str] = list(_PIPELINE.get_labels())
_LABEL_TO_ID: dict[str, int] = {label: idx for idx, label in enumerate(_LABELS)}

# The CTC blank index (always 0 for this pipeline).
_BLANK_ID: int = _LABEL_TO_ID.get("-", 0)

print(f"[alignment_service] Ready  ·  vocab size = {len(_LABELS)}  ·  blank = {_BLANK_ID}")


# ── Public API ───────────────────────────────────────────────────────────────

def align_audio_to_text(
    file_path: str,
    transcript: str,
) -> List[Dict[str, float | str]]:
    """Perform forced alignment between an audio file and a transcript.

    Parameters
    ----------
    file_path : str
        Path to the audio file (any format supported by ``torchaudio.load``).
    transcript : str
        The verbatim transcript of the audio (output of Stage 1 — Whisper).

    Returns
    -------
    list[dict]
        A list of word-level alignment results, e.g.::

            [
                {"word": "THE",  "start": 0.42, "end": 0.54},
                {"word": "CAT",  "start": 0.56, "end": 0.72},
                ...
            ]
    """
    start_wall = time.perf_counter()

    # ── 1. Load & preprocess audio ───────────────────────────────────────
    waveform, sample_rate = _load_and_preprocess_audio(file_path)

    # ── 2. Clean / normalise transcript & tokenise ───────────────────────
    tokens, cleaned_words = _normalise_and_tokenise(transcript)

    if len(tokens) == 0:
        print("[alignment_service] WARNING: transcript produced zero tokens.")
        return []

    # ── 3. Compute CTC log-probability emissions ────────────────────────
    log_probs, num_frames = _compute_emissions(waveform)

    # ── 4. Run forced alignment ─────────────────────────────────────────
    aligned_tokens, scores = _run_forced_align(log_probs, tokens, num_frames)

    # ── 5. Merge character alignment into word-level timestamps ─────────
    words = _merge_to_words(aligned_tokens, scores, cleaned_words, num_frames)

    elapsed = time.perf_counter() - start_wall
    print(f"[alignment_service] Aligned {len(words)} words in {elapsed:.3f}s")

    return words


# ── Internal helpers ─────────────────────────────────────────────────────────

def _load_and_preprocess_audio(file_path: str) -> tuple[torch.Tensor, int]:
    """Load audio, convert to mono, and resample to ``MODEL_SAMPLE_RATE``."""
    waveform, sample_rate = torchaudio.load(file_path)
    # waveform shape: (channels, samples)

    # Stereo → mono
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)  # (1, samples)

    # Resample if the file's sample rate differs from the model's expected rate
    if sample_rate != MODEL_SAMPLE_RATE:
        print(
            f"[alignment_service] Resampling {sample_rate} Hz → {MODEL_SAMPLE_RATE} Hz"
        )
        resampler = torchaudio.transforms.Resample(
            orig_freq=sample_rate, new_freq=MODEL_SAMPLE_RATE
        )
        waveform = resampler(waveform)

    return waveform, MODEL_SAMPLE_RATE


def _normalise_and_tokenise(
    transcript: str,
) -> tuple[list[int], list[str]]:
    """Clean the transcript and convert it to a list of CTC token IDs.

    **Critical safeguard:** Any character not present in the Wav2Vec2 label
    vocabulary is silently stripped so that downstream ``_LABEL_TO_ID[ch]``
    look-ups never raise ``KeyError``.

    Returns
    -------
    tokens : list[int]
        Flat list of token IDs (including ``|`` word-boundary tokens).
    cleaned_words : list[str]
        The individual words *after* cleaning (uppercase, alpha-only).
    """
    # Uppercase everything — model labels are uppercase A-Z plus "|" and "-"
    text = transcript.upper()

    # Strip ALL characters that are NOT uppercase letters or whitespace.
    # This removes punctuation, digits, quotes, etc.
    text = re.sub(r"[^A-Z\s]", "", text)

    # Collapse multiple spaces and strip leading/trailing whitespace
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        return [], []

    # Split into words for later word-level merge
    cleaned_words = text.split()

    # Replace spaces with the pipe separator that the model uses for word
    # boundaries, then convert to a flat character sequence.
    token_str = "|".join(cleaned_words)  # e.g. "THE|CAT|SAT"

    # Map each character to its token ID
    tokens: list[int] = []
    for ch in token_str:
        if ch in _LABEL_TO_ID:
            tokens.append(_LABEL_TO_ID[ch])
        # Characters not in the vocabulary are silently dropped.

    return tokens, cleaned_words


def _compute_emissions(waveform: torch.Tensor) -> tuple[torch.Tensor, int]:
    """Forward-pass through Wav2Vec2 to obtain log-softmax CTC emissions.

    Parameters
    ----------
    waveform : Tensor
        Shape ``(1, samples)`` — mono, 16 kHz.

    Returns
    -------
    log_probs : Tensor
        Shape ``(1, T, C)`` — batch-first log-probabilities.
    num_frames : int
        ``T`` — number of CTC frames produced by the model.
    """
    with torch.inference_mode():
        # Model expects (batch, samples).  waveform is already (1, samples).
        emissions, _ = _MODEL(waveform.to(DEVICE))
        # emissions shape: (1, T, C) — raw logits

    # Apply log-softmax to convert logits → log-probabilities.
    # This prevents numerical underflow during alignment scoring.
    log_probs = torch.log_softmax(emissions, dim=-1)  # (1, T, C)

    num_frames = log_probs.size(1)
    return log_probs, num_frames


def _run_forced_align(
    log_probs: torch.Tensor,
    tokens: list[int],
    num_frames: int,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Wrap ``torchaudio.functional.forced_align`` with correct tensor shapes.

    Parameters
    ----------
    log_probs : Tensor
        ``(1, T, C)`` — log-probability emissions.
    tokens : list[int]
        Flat list of target token IDs (length ``L``).
    num_frames : int
        ``T`` — total CTC frames.

    Returns
    -------
    aligned_tokens : Tensor
        ``(1, T)`` — per-frame token label (includes blank frames).
    scores : Tensor
        ``(1, T)`` — per-frame alignment log-probability score.
    """
    # ── Build target tensor  (B=1, L) ────────────────────────────────────
    targets = torch.tensor([tokens], dtype=torch.int32, device=log_probs.device)
    # targets shape: (1, L)

    # ── Build length tensors  (B=1,) ─────────────────────────────────────
    input_lengths = torch.tensor([num_frames], dtype=torch.int32, device=log_probs.device)
    target_lengths = torch.tensor([len(tokens)], dtype=torch.int32, device=log_probs.device)

    # Move log_probs to CPU for the alignment call (torchaudio forced_align
    # operates on CPU tensors in many builds).
    log_probs_cpu = log_probs.cpu()
    targets_cpu = targets.cpu()
    input_lengths_cpu = input_lengths.cpu()
    target_lengths_cpu = target_lengths.cpu()

    aligned_tokens, scores = torchaudio.functional.forced_align(
        log_probs=log_probs_cpu,     # (1, T, C)
        targets=targets_cpu,          # (1, L)
        input_lengths=input_lengths_cpu,   # (1,)
        target_lengths=target_lengths_cpu, # (1,)
        blank=_BLANK_ID,
    )
    # aligned_tokens shape: (1, T)  — token label per frame
    # scores         shape: (1, T)  — log-prob per frame

    return aligned_tokens, scores


def _merge_to_words(
    aligned_tokens: torch.Tensor,
    scores: torch.Tensor,
    cleaned_words: list[str],
    num_frames: int,
) -> List[Dict[str, float | str]]:
    """Aggregate character-level frame alignment into word-level timestamps.

    Each frame spans ``frame_duration`` seconds.  We walk the alignment
    output, accumulate non-blank / non-separator characters into the
    current word, and emit a word entry every time we encounter a ``|``
    separator or reach the end of the alignment.

    Parameters
    ----------
    aligned_tokens : Tensor
        ``(1, T)`` — per-frame token label.
    scores : Tensor
        ``(1, T)`` — per-frame score (unused here but available for
        confidence metrics in later stages).
    cleaned_words : list[str]
        Ordered list of words as they appear in the normalised transcript.
    num_frames : int
        Total number of CTC frames (``T``).

    Returns
    -------
    list[dict]
        Word-level alignment with ``word``, ``start`` (seconds), ``end``
        (seconds) keys.
    """
    # Duration of a single CTC output frame (seconds).
    # The Wav2Vec2 encoder downsamples by a factor of 320 at 16 kHz,
    # so each frame = 320 / 16_000 = 0.020 s  (20 ms).
    frame_duration: float = 320.0 / MODEL_SAMPLE_RATE  # 0.02 s

    # Squeeze the batch dimension: (1, T) → (T,)
    token_ids = aligned_tokens.squeeze(0).tolist()  # list[int], length T

    # Separator token ID ("|")
    separator_id = _LABEL_TO_ID.get("|", -1)

    words: list[dict[str, float | str]] = []
    word_idx = 0  # pointer into cleaned_words

    # Track the frame range for the current word being accumulated.
    word_start_frame: int | None = None

    for frame_idx, tok_id in enumerate(token_ids):
        # Skip blank frames — they carry no label information.
        if tok_id == _BLANK_ID:
            continue

        # Word-boundary separator "|"
        if tok_id == separator_id:
            # Finalise the current word if we have accumulated frames.
            if word_start_frame is not None and word_idx < len(cleaned_words):
                words.append({
                    "word": cleaned_words[word_idx],
                    "start": round(word_start_frame * frame_duration, 3),
                    "end": round(frame_idx * frame_duration, 3),
                })
                word_idx += 1
                word_start_frame = None
            continue

        # Regular character token — mark start of a new word if needed.
        if word_start_frame is None:
            word_start_frame = frame_idx

    # Finalise the last word (there is no trailing "|").
    if word_start_frame is not None and word_idx < len(cleaned_words):
        # Use the last frame that had a non-blank token as the end boundary.
        # Walk backwards to find it.
        last_active_frame = num_frames - 1
        for f in range(num_frames - 1, -1, -1):
            if token_ids[f] != _BLANK_ID:
                last_active_frame = f
                break

        words.append({
            "word": cleaned_words[word_idx],
            "start": round(word_start_frame * frame_duration, 3),
            "end": round((last_active_frame + 1) * frame_duration, 3),
        })

    return words
