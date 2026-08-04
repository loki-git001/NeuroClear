# scripts/test_pipeline.py
# ──────────────────────────────────────────────────────────────────────────────
# End-to-end smoke test for the NeuroClear pipeline:
#   Stage 1  →  Whisper transcription   (whisper_service)
#   Stage 2  →  Forced alignment        (alignment_service)
#   Stage 3  →  Audio slicing           (slicer_service)
#   Stage 4  →  Clinical scoring        (scoring_service)
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
from services.scoring_service import (
    calculate_prosody_metrics,
    detect_stutters,
    detect_false_starts,
)

# ── Configuration ────────────────────────────────────────────────────────────
AUDIO_FILE = os.path.join(_PROJECT_ROOT, "data", "raw", "sample_2.wav")


def main() -> None:
    """Run the four-stage NeuroClear pipeline and print results."""
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
    # transcript: str = "This is a Python string method that left-justifies a string by padding"

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
        conf = f"{entry.get('confidence', 0.0):.3f}"
        print(f"  Word: {word} | Start: {start} | End: {end} | Conf: {conf}")

    print()
    print(f"  Total words aligned: {len(alignments)}")
    print("=" * 60)

    # ── Stage 3: Audio Slicing ────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  STAGE 3 — Audio Slicer")
    print("=" * 60)

    slices = slice_audio_by_words(AUDIO_FILE, alignments, sample_rate=16000)

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

    # ── Stage 4: Clinical Scoring ───────────────────────────────────────
    print("\n" + "=" * 60)
    print("  STAGE 4 — Clinical Scoring")
    print("=" * 60)

    # Calculate total audio duration from the alignment boundaries.
    # Use the end time of the last word as a conservative estimate.
    total_audio_duration: float = alignments[-1]["end"] if alignments else 0.0

    # ── 4a. False Start / Pre-Voicing Tremor Detection ───────────
    false_starts = detect_false_starts(AUDIO_FILE, alignments)
    fs_flagged = [f for f in false_starts if f.get("false_start_flag")]

    print("\n  ┌─ False Start / Pre-Voicing Tremors (Gap Analysis) ──────┐")
    if fs_flagged:
        for f in fs_flagged:
            before = f["before_word"]
            after = f["after_word"]
            dur = f"{f['gap_duration']:.3f}s"
            tremor = f"{f['active_tremor_time']:.3f}s"
            silence = f"{f['true_silent_time']:.3f}s"
            peaks = f["peak_count"]
            print(
                f"  │  ⚠  [{before}] ─(gap: {dur})─ [{after}]\n"
                f"  │      Struggle: {tremor} | Silence: {silence} | peaks={peaks}  FLAGGED"
            )
    else:
        print("  │  ✔  No false starts / pre-voicing tremors detected.")
    print("  └────────────────────────────────────────────────────────┘")

    # ── 4b. Prosody Metrics ─────────────────────────────────────────
    # We pass false_starts so the prosody calculator can exclude active tremor time.
    prosody = calculate_prosody_metrics(alignments, total_audio_duration, false_starts)

    print("\n  ┌─ Prosody Metrics ──────────────────────────────────────┐")
    print(f"  │  Speaking Rate      : {prosody['words_per_minute']} WPM")
    print(f"  │  Average Gap        : {prosody['avg_gap']}s")
    print(f"  │  Max Gap            : {prosody['max_gap']}s")
    print(f"  │  Pauses > 0.5s      : {prosody['total_pauses_over_half_sec']}")

    if prosody["gap_details"]:
        print("  │")
        print("  │  Notable pauses:")
        for g in prosody["gap_details"]:
            print(f"  │    {g['between']}  ({g['gap']}s)")

    print("  └────────────────────────────────────────────────────────┘")

    # ── 4c. Articulation Confidence ────────────────────────────────
    print("\n  ┌─ Articulation Confidence (CTC log-prob) ───────────────┐")
    for entry in alignments:
        word = entry["word"].ljust(max_word_len)
        conf = entry.get("confidence", 0.0)
        # Build a simple visual bar (scaled: -10 = empty, 0 = full)
        bar_len = max(0, int((conf + 10) * 2))  # 0..20 chars
        bar = "█" * bar_len + "░" * (20 - bar_len)
        print(f"  │  {word}  {conf:+.3f}  {bar}")
    print("  └────────────────────────────────────────────────────────┘")

    # ── 4d. Motor Tremor / Stutter Detection ───────────────────────
    stutter_results = detect_stutters(slices)
    flagged = [s for s in stutter_results if s.get("stutter_flag")]

    print("\n  ┌─ Motor Tremor / Stutter Flags ──────────────────────────┐")
    if flagged:
        for s in flagged:
            word = s["word"].ljust(max_word_len)
            syl = s.get("syllable_estimate", "?")
            allowed = s.get("allowed_peaks", "?")
            peaks = s["peak_count"]
            print(
                f"  │  ⚠  {word}  syllables={syl}  "
                f"allowed={allowed}  peaks={peaks}  FLAGGED"
            )
    else:
        print("  │  ✔  No stutter/tremor patterns detected.")
    print("  └────────────────────────────────────────────────────────┘")

    print("\n" + "=" * 60)
    print("  PIPELINE COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
