# services/scoring_service.py
# ──────────────────────────────────────────────────────────────────────────────
# Stage 4 — Clinical Scoring Service
#
# Provides two core clinical analysis functions:
#   1. Prosody metrics  — speaking rate, pause distribution, inter-word gaps.
#   2. Stutter/tremor detection — DSP envelope analysis with peak detection
#      to flag words that exhibit repetitive motor bursts.
# ──────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from typing import List, Dict, Any

import numpy as np
import torchaudio
from scipy.signal import find_peaks


# ── 1. Prosody Metrics ───────────────────────────────────────────────────────

def calculate_prosody_metrics(
    alignments: List[Dict[str, Any]],
    total_audio_duration: float,
    false_starts: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Compute clinical prosody metrics from word-level alignment data.

    Analyses the temporal distribution of speech by measuring inter-word
    silence gaps and overall speaking rate.  These metrics are standard
    indicators of dysarthric speech patterns such as bradykinesia
    (abnormally slow speech) and irregular pausing.

    Parameters
    ----------
    alignments : list[dict]
        Word-level alignment results from Stage 2, each containing
        ``word``, ``start``, and ``end`` keys (times in seconds).
    total_audio_duration : float
        Total duration of the source audio file in seconds.
    false_starts : list[dict], optional
        Results from ``detect_false_starts``.  If provided, actively
        stuttered gap time is excluded from the silence calculations
        to prevent double-penalising the same event.

    Returns
    -------
    dict
        ``max_gap``                 – Longest silence gap (seconds).
        ``avg_gap``                 – Mean silence gap (seconds, 3 decimals).
        ``total_pauses_over_half_sec`` – Count of gaps > 0.5 s.
        ``words_per_minute``        – Speaking rate (WPM, 1 decimal).
        ``gap_details``             – List of dicts describing each gap > 0.5 s
                                      with the flanking word pair.
    """
    gaps: list[float] = []
    gap_details: list[dict[str, Any]] = []

    # Create a lookup for fast gap filtering
    fs_lookup = {round(fs["gap_start"],4): fs for fs in (false_starts or [])}

    # Walk consecutive word pairs and measure the silence between them.
    for i in range(len(alignments) - 1):
        current_end: float = round(alignments[i]["end"], 4)
        next_start: float = round(alignments[i + 1]["start"], 4)
        gap = round(next_start - current_end, 4)

        if gap > 0:
            # If this gap was flagged as a false start, extract the true silence
            if current_end in fs_lookup and fs_lookup[current_end]["false_start_flag"]:
                true_silence = fs_lookup[current_end]["true_silent_time"]
                if true_silence > 0:
                    gaps.append(true_silence)
                    if true_silence > 0.5:
                        gap_details.append({
                            "between": f"{alignments[i]['word']} → {alignments[i + 1]['word']}",
                            "gap": true_silence,
                        })
            # Otherwise, use the full gap
            else:
                gaps.append(gap)
                if gap > 0.5:
                    gap_details.append({
                        "between": f"{alignments[i]['word']} → {alignments[i + 1]['word']}",
                        "gap": gap,
                    })

    max_gap: float = round(max(gaps), 3) if gaps else 0.0
    avg_gap: float = round(sum(gaps) / len(gaps), 3) if gaps else 0.0

    # Speaking rate — guard against zero-length audio.
    if total_audio_duration > 0:
        wpm = round((len(alignments) / total_audio_duration) * 60, 1)
    else:
        wpm = 0.0

    pauses_over_half_sec = len(gap_details)

    return {
        "max_gap": max_gap,
        "avg_gap": avg_gap,
        "total_pauses_over_half_sec": pauses_over_half_sec,
        "words_per_minute": wpm,
        "gap_details": gap_details,
    }


# ── 2. Syllable Estimation (helper) ──────────────────────────────────────────

def _estimate_syllables(word: str) -> int:
    """Estimate the number of syllables in a word by counting vowel groups.

    Uses a simple heuristic:
      1. Walk the characters and count contiguous vowel clusters.
      2. Apply a silent-'e' correction: if the word ends in 'E' (but NOT
         'LE', which is a genuinely pronounced syllable as in BOTTLE/SIMPLE),
         subtract one group — the trailing 'E' is typically silent.
      3. Clamp the result to a minimum of 1 (every word has ≥ 1 syllable).

    Parameters
    ----------
    word : str
        The word to analyse (expected uppercase from alignment output).

    Returns
    -------
    int
        Estimated syllable count (≥ 1).
    """
    word = word.upper()
    vowels = set("AEIOUY")

    # Count contiguous vowel groups.
    groups: int = 0
    in_vowel: bool = False

    for ch in word:
        if ch in vowels:
            if not in_vowel:
                groups += 1
                in_vowel = True
        else:
            in_vowel = False

    # Silent-'e' correction:
    # Words ending in 'E' (like VOLUME, MAKE) usually have a silent final 'e',
    # UNLESS they end in 'LE' (like BOTTLE, SIMPLE) where '-le' is pronounced.
    if word.endswith("E") and groups > 1 and not word.endswith("LE"):
        groups -= 1

    # Every word has at least 1 syllable (guards against consonant-only
    # fragments like "HMM", "SHH", abbreviations, etc.).
    return max(1, groups)


# ── 3. Stutter / Tremor Detection ────────────────────────────────────────────

def detect_stutters(
    slices: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Analyse per-word audio slices for motor tremor / stutter indicators.

    For each word clip the function:
      1. Estimates the word's syllable count via ``_estimate_syllables``.
      2. Loads and normalises the waveform.
      3. Computes a smoothed amplitude envelope via a 25 ms moving average.
      4. Runs ``scipy.signal.find_peaks`` to detect repetitive energy bursts.

    A word is flagged only if its detected peak count exceeds
    ``syllable_count + 1`` (the +1 buffer reduces false positives on
    multi-syllable words like HOSPITAL that naturally produce multiple
    energy arcs).

    Parameters
    ----------
    slices : list[dict]
        Slice metadata from Stage 3 (``slicer_service``).  Each dict must
        contain at least ``word`` (str) and ``file`` (str, absolute path
        to the .wav clip).

    Returns
    -------
    list[dict]
        The same slice dictionaries, augmented with:
        ``stutter_flag`` (bool), ``peak_count`` (int),
        ``syllable_estimate`` (int), and ``allowed_peaks`` (int).
    """
    results: list[dict[str, Any]] = []

    for s in slices:
        entry = dict(s)  # shallow copy so we don't mutate the caller's data

        try:
            waveform, sr = torchaudio.load(s["file"])
            # waveform shape: (channels, samples)

            # Multi-channel → mono
            if waveform.shape[0] > 1:
                waveform = waveform.mean(dim=0, keepdim=True)

            # Convert to a 1-D NumPy array for DSP processing.
            audio_np: np.ndarray = waveform.squeeze().numpy()

            # ── Normalise amplitude (CRITICAL) ───────────────────────────
            # Microphones / recording levels vary widely; without this step
            # the prominence threshold becomes meaningless.
            max_val = np.max(np.abs(audio_np))
            if max_val > 0:
                audio_np = audio_np / max_val

            # ── Compute smoothed amplitude envelope ──────────────────────
            abs_audio = np.abs(audio_np)

            # Moving-average window: 400 samples = 25 ms at 16 kHz.
            window_size = 400
            if len(abs_audio) >= window_size:
                smoothed = np.convolve(
                    abs_audio,
                    np.ones(window_size) / window_size,
                    mode="valid",
                )
            else:
                # Audio shorter than one window — use what we have.
                smoothed = abs_audio

            # ── Peak detection ───────────────────────────────────────────
            # prominence = 0.05  → ignores tiny ripples in the envelope.
            # distance   = 1600  → peaks must be ≥ 0.1 s apart (at 16 kHz).
            peaks, _ = find_peaks(smoothed, prominence=0.05, distance=1600)

            peak_count = len(peaks)

            # ── Syllable-aware dynamic threshold ─────────────────────
            # A multi-syllable word naturally produces one energy arc per
            # syllable.  We only flag stutters when the peak count exceeds
            # the expected syllable count plus a +1 tolerance buffer.
            syllables = _estimate_syllables(s["word"])
            allowed_peaks = syllables + 1

            entry["syllable_estimate"] = syllables
            entry["allowed_peaks"] = allowed_peaks
            entry["peak_count"] = peak_count
            entry["stutter_flag"] = peak_count > allowed_peaks

        except Exception as e:
            print(
                f"[scoring_service] WARNING: Could not analyse slice "
                f"'{s.get('word', '?')}': {e}"
            )
            entry["stutter_flag"] = False
            entry["peak_count"] = 0

        results.append(entry)

    return results


# ── 4. False Start / Pre-Voicing Tremor Detection ────────────────────────────

# Minimum gap duration (seconds) to consider for analysis.
# Gaps shorter than this are normal coarticulation transitions.
_MIN_GAP_DURATION: float = 0.2

# RMS energy floor — if the gap's RMS is below this threshold (relative to
# the globally-normalised waveform), it's genuine silence and we skip it.
# This prevents noise amplification from producing false-positive peaks.
_RMS_NOISE_FLOOR: float = 0.02


def detect_false_starts(
    file_path: str,
    alignments: List[Dict[str, Any]],
    *,
    sample_rate: int = 16_000,
) -> List[Dict[str, Any]]:
    """Detect pre-voicing tremors / false starts hidden in inter-word gaps.

    Whisper often drops stuttered phonemes (e.g. "m-m-" before "method"),
    so they never appear in the transcript.  This function examines the
    audio *between* aligned words to find unexpected vocal energy.

    Strategy:
      1. Load the **full** audio and normalise it **once** against its
         global peak amplitude.  This ensures that genuine silence stays
         near zero and real stutters retain their relative energy.
      2. For every inter-word gap ≥ ``_MIN_GAP_DURATION`` seconds, slice
         the globally-normalised waveform.
      3. Check the gap's RMS energy against ``_RMS_NOISE_FLOOR``.
         If below, the gap is genuine silence — skip it.
      4. If above, run the standard envelope + ``find_peaks`` algorithm.
         Any detected peaks indicate vocalisation in a region that should
         be silent — a high-confidence indicator of stuttering, lip
         smacking, or a false start.

    Parameters
    ----------
    file_path : str
        Path to the source audio file.
    alignments : list[dict]
        Word-level alignment results from Stage 2, each containing
        ``word``, ``start``, and ``end`` keys (times in seconds).
    sample_rate : int
        Sample rate of the audio (default 16 kHz).  Used to convert
        timestamps to sample indices.

    Returns
    -------
    list[dict]
        One entry per analysed gap (only gaps ≥ ``_MIN_GAP_DURATION``),
        each containing::

            {
                "before_word": str,       # Word preceding the gap
                "after_word": str,        # Word following the gap
                "gap_start": float,       # Gap start time (seconds)
                "gap_end": float,         # Gap end time (seconds)
                "gap_duration": float,    # Gap length (seconds)
                "rms_energy": float,      # RMS energy of the gap
                "peak_count": int,        # Envelope peaks detected
                "false_start_flag": bool, # True if peaks > 0
                "active_tremor_time": float, # Duration of struggle (seconds)
                "true_silent_time": float,   # Remaining true silence (seconds)
            }
    """
    if len(alignments) < 2:
        return []

    # ── 1. Load full audio & normalise globally ──────────────────────────
    try:
        waveform, sr = torchaudio.load(file_path)
    except Exception as e:
        print(f"[scoring_service] ERROR: Could not load audio for gap analysis: {e}")
        return []

    # Stereo → mono
    if waveform.shape[0] > 1:
        waveform = waveform.mean(dim=0, keepdim=True)

    # Resample if needed
    if sr != sample_rate:
        resampler = torchaudio.transforms.Resample(orig_freq=sr, new_freq=sample_rate)
        waveform = resampler(waveform)

    # Convert to 1-D NumPy array
    full_audio: np.ndarray = waveform.squeeze().numpy()

    # Global normalisation — this is the KEY difference from per-slice
    # normalisation.  Silence stays near 0; speech stays at full scale.
    global_max = np.max(np.abs(full_audio))
    if global_max > 0:
        full_audio = full_audio / global_max

    # ── 2. Analyse each inter-word gap ───────────────────────────────────
    results: list[dict[str, Any]] = []

    for i in range(len(alignments) - 1):
        word_a = alignments[i]
        word_b = alignments[i + 1]

        gap_start_sec: float = word_a["end"]
        gap_end_sec: float = word_b["start"]
        gap_duration: float = round(gap_end_sec - gap_start_sec, 3)

        # Skip gaps that are too short — they're normal transitions.
        if gap_duration < _MIN_GAP_DURATION:
            continue

        # Convert seconds → sample indices
        start_sample = int(gap_start_sec * sample_rate)
        end_sample = int(gap_end_sec * sample_rate)

        # Clamp to waveform bounds
        start_sample = max(0, start_sample)
        end_sample = min(len(full_audio), end_sample)

        if end_sample <= start_sample:
            continue

        gap_audio = full_audio[start_sample:end_sample]

        # ── 3. RMS energy floor check ────────────────────────────────
        rms_energy = float(np.sqrt(np.mean(gap_audio ** 2)))

        entry: dict[str, Any] = {
            "before_word": word_a["word"],
            "after_word": word_b["word"],
            "gap_start": gap_start_sec,
            "gap_end": gap_end_sec,
            "gap_duration": gap_duration,
            "rms_energy": round(rms_energy, 4),
            "peak_count": 0,
            "false_start_flag": False,
            "active_tremor_time": 0.0,
            "true_silent_time": gap_duration,
        }

        if rms_energy < _RMS_NOISE_FLOOR:
            # Genuine silence — no need to run peak detection.
            results.append(entry)
            continue

        # ── 4. Envelope + peak detection (same DSP as word analysis) ─
        abs_audio = np.abs(gap_audio)

        window_size = 400  # 25 ms at 16 kHz
        if len(abs_audio) >= window_size:
            smoothed = np.convolve(
                abs_audio,
                np.ones(window_size) / window_size,
                mode="valid",
            )
        else:
            smoothed = abs_audio

        peaks, _ = find_peaks(smoothed, prominence=0.05, distance=1600)

        # ── 5. Dynamic Gap Partitioning ──────────────────────────────
        # Calculate exactly how much of this gap was struggle vs silence.
        active_tremor_time = 0.0
        true_silent_time = gap_duration

        if len(peaks) > 0:
            # peaks array contains sample indices within the gap slice.
            first_peak_time = peaks[0] / sample_rate
            last_peak_time = peaks[-1] / sample_rate

            struggle_duration = last_peak_time - first_peak_time
            # +0.2s buffer (0.1s front, 0.1s tail) for acoustic footprint
            active_tremor = struggle_duration + 0.2

            # Guard rails: clamp to total gap duration
            active_tremor_time = min(active_tremor, gap_duration)
            true_silent_time = max(0.0, gap_duration - active_tremor_time)

        entry["peak_count"] = len(peaks)
        # ANY peak in a supposedly silent gap is abnormal.
        entry["false_start_flag"] = len(peaks) > 0
        entry["active_tremor_time"] = round(active_tremor_time, 3)
        entry["true_silent_time"] = round(true_silent_time, 3)

        results.append(entry)

    flagged_count = sum(1 for r in results if r["false_start_flag"])
    print(
        f"[scoring_service] Gap analysis: {len(results)} gaps checked, "
        f"{flagged_count} false start(s) detected"
    )

    return results

