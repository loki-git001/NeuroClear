# services/slicer_service.py
# ──────────────────────────────────────────────────────────────────────────────
# Stage 3 — Audio Slicer
#
# Takes the word-level alignment results from Stage 2 and slices the source
# audio into individual per-word .wav files using PyTorch tensor slicing.
#
# Why tensor slicing over soundfile?
#   • The waveform is loaded once into memory as a contiguous tensor.
#   • Slicing (waveform[:, start:end]) is a zero-copy view — no data is
#     copied until torchaudio.save materialises the slice to disk.
#   • No repeated file I/O for each word; only one torchaudio.load call.
# ──────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import os
import time
from typing import List, Dict

import torch
import torchaudio


def slice_audio_by_words(
    file_path: str,
    alignments: List[Dict[str, float | str]],
    output_dir: str | None = None,
    *,
    sample_rate: int | None = None,
) -> List[Dict[str, str]]:
    """Slice an audio file into individual word-level .wav segments.

    Parameters
    ----------
    file_path : str
        Path to the source audio file.
    alignments : list[dict]
        Word-level alignment results from ``align_audio_to_text``, e.g.::

            [{"word": "THE", "start": 0.42, "end": 0.54}, ...]

    output_dir : str | None
        Directory to write sliced .wav files into.  Defaults to
        ``data/sliced/<source_stem>/`` relative to the project root.
    sample_rate : int | None
        If provided, the audio is resampled to this rate before slicing.
        By default the audio is saved at its **original** sample rate to
        preserve maximum fidelity.

    Returns
    -------
    list[dict]
        Metadata for every saved slice::

            [
                {
                    "word": "THE",
                    "index": 0,
                    "start": 0.42,
                    "end": 0.54,
                    "duration": 0.12,
                    "file": "/abs/path/to/000_THE.wav",
                },
                ...
            ]
    """
    start_wall = time.perf_counter()

    # ── 1. Load audio ────────────────────────────────────────────────────
    waveform, orig_sr = torchaudio.load(file_path)
    # waveform shape: (channels, samples)

    # Convert stereo → mono so every slice is single-channel.
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)  # (1, samples)

    # Optional resampling (e.g. to normalise everything to 16 kHz).
    effective_sr = orig_sr
    if sample_rate is not None and sample_rate != orig_sr:
        print(f"[slicer_service] Resampling {orig_sr} Hz → {sample_rate} Hz")
        resampler = torchaudio.transforms.Resample(
            orig_freq=orig_sr, new_freq=sample_rate
        )
        waveform = resampler(waveform)
        effective_sr = sample_rate

    # ── 2. Resolve output directory ──────────────────────────────────────
    if output_dir is None:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        source_stem = os.path.splitext(os.path.basename(file_path))[0]
        output_dir = os.path.join(project_root, "data", "sliced", source_stem)

    os.makedirs(output_dir, exist_ok=True)

    # ── 3. Slice & save each word ────────────────────────────────────────
    results: list[dict[str, str | float | int]] = []

    for idx, entry in enumerate(alignments):
        word: str = entry["word"]
        start_sec: float = entry["start"]
        end_sec: float = entry["end"]

        # Convert seconds → sample indices at the effective sample rate.
        start_frame = int(start_sec * effective_sr)
        end_frame = int(end_sec * effective_sr)

        # Clamp to waveform bounds to prevent out-of-range slicing.
        start_frame = max(0, start_frame)
        end_frame = min(waveform.shape[1], end_frame)

        if end_frame <= start_frame:
            print(
                f"[slicer_service] WARNING: skipping '{word}' — "
                f"empty slice ({start_sec:.3f}s → {end_sec:.3f}s)"
            )
            continue

        # Zero-copy tensor view of just this word's audio.
        word_waveform = waveform[:, start_frame:end_frame]  # (1, N)

        # File name: zero-padded index + uppercase word, e.g. "003_CHECK.wav"
        filename = f"{idx:03d}_{word}.wav"
        out_path = os.path.join(output_dir, filename)

        torchaudio.save(out_path, word_waveform, effective_sr)

        duration = round(end_sec - start_sec, 3)

        results.append({
            "word": word,
            "index": idx,
            "start": start_sec,
            "end": end_sec,
            "duration": duration,
            "file": os.path.abspath(out_path),
        })

    elapsed = time.perf_counter() - start_wall
    print(
        f"[slicer_service] Saved {len(results)} word clips "
        f"to {output_dir}  ({elapsed:.3f}s)"
    )

    return results
