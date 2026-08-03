# scripts/test_pipeline.py
# ──────────────────────────────────────────────────────────────────────────────
# End-to-end smoke test for the NeuroClear pipeline:
#   Stage 1  →  Whisper transcription   (whisper_service)
#   Stage 2  →  Forced alignment        (alignment_service)
#   Stage 3  →  Audio slicing           (slicer_service)
# ──────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import os
import sys

# Ensure the project root is on sys.path so that `services.*` imports resolve
# regardless of where the script is invoked from.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from services.whisper_service import transcribe_audio_file
from services.alignment_service import align_audio_to_text
from services.slicer_service import slice_audio_by_words

# ── Configuration ────────────────────────────────────────────────────────────
AUDIO_FILE = os.path.join(_PROJECT_ROOT, "data", "raw", "sample.wav")


def main() -> None:
    """Run the two-stage NeuroClear pipeline and print results."""
    # Verify the sample file exists before we kick off model inference.
    if not os.path.isfile(AUDIO_FILE):
        print(f"ERROR: Audio file not found → {AUDIO_FILE}")
        print("Place a .wav file at  data/raw/sample.wav  and re-run.")
        sys.exit(1)

    # ── Stage 1: Transcription (Whisper) ─────────────────────────────────
    print("\n" + "=" * 60)
    print("  STAGE 1 — Whisper Transcription")
    print("=" * 60)

    whisper_result = transcribe_audio_file(AUDIO_FILE)
    transcript: str = whisper_result["text"]

    print(f"\n  Transcript : {transcript}")
    print(f"  Inference  : {whisper_result['inference_time_seconds']}s")

    # ── Stage 2: Forced Alignment ────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  STAGE 2 — Forced Alignment (Wav2Vec2)")
    print("=" * 60)

    alignments = align_audio_to_text(AUDIO_FILE, transcript)

    if not alignments:
        print("\n  No alignment results (empty transcript?).")
        return

    # ── Pretty-print word-level timestamps ───────────────────────────────
    # Determine the longest word for neat column alignment.
    max_word_len = max(len(entry["word"]) for entry in alignments)

    print()
    for entry in alignments:
        word = entry["word"].ljust(max_word_len)
        start = f"{entry['start']:.2f}s"
        end = f"{entry['end']:.2f}s"
        print(f"  Word: {word} | Start: {start} | End: {end}")

    print()
    print(f"  Total words aligned: {len(alignments)}")
    print("=" * 60)

    # ── Stage 3: Audio Slicing ────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  STAGE 3 — Audio Slicer")
    print("=" * 60)

    slices = slice_audio_by_words(AUDIO_FILE, alignments)

    if not slices:
        print("\n  No slices produced.")
        return

    print()
    for s in slices:
        word = s["word"].ljust(max_word_len)
        dur = f"{s['duration']:.3f}s"
        print(f"  {s['index']:03d}  {word}  {dur}  →  {os.path.basename(s['file'])}")

    print()
    print(f"  Total clips saved: {len(slices)}")
    print(f"  Output directory : {os.path.dirname(slices[0]['file'])}")
    print("=" * 60)


if __name__ == "__main__":
    main()
