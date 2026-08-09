# services/llm_service.py
# ──────────────────────────────────────────────────────────────────────────────
# Stage 5 — LLM Clinical Report Generation
#
# Sends the aggregated pipeline metrics to the Gemini API and returns a
# rigorous, structured clinical assessment formatted as a Pydantic model
# (and serialised to dict) for downstream consumption.
#
# API pattern: google-genai Interactions API (>= 2.3.0)
#   client.interactions.create(..., response_format={"schema": ...})
# ──────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field

from .cancellation import CancellationToken

# ── Load environment & initialise client ────────────────────────────────────
load_dotenv()

_api_key = os.getenv("GEMINI_API_KEY")
if not _api_key:
    raise EnvironmentError(
        "[llm_service] GEMINI_API_KEY not found. "
        "Add it to your .env file as: GEMINI_API_KEY=<your_key>"
    )

_client = genai.Client(api_key=_api_key)

_MODEL = "gemini-3.6-flash"


# ── Pydantic schema — the enforced JSON output shape ────────────────────────

class WordArticulationFlag(BaseModel):
    """Per-word articulation concern raised by the model."""
    word: str = Field(description="The flagged word.")
    ctc_confidence: float = Field(
        description="CTC log-probability confidence score from Wav2Vec2 "
                    "(0.0 = perfect, more negative = worse)."
    )
    clinical_interpretation: str = Field(
        description="One-sentence clinical interpretation of this word's "
                    "articulation quality."
    )


class StutterEvent(BaseModel):
    """A stutter or false-start event detected by the DSP pipeline."""
    event_type: str = Field(
        description="One of: 'within_word_tremor', 'pre_voicing_false_start'."
    )
    target_word: str = Field(
        description="The word during or before which the event occurred."
    )
    clinical_note: str = Field(
        description="Brief clinical note describing the significance of this event."
    )


class SpeechExercise(BaseModel):
    """A targeted clinical speech exercise recommendation."""
    exercise_name: str = Field(description="Short name of the exercise.")
    target_deficit: str = Field(
        description="The specific dysarthric deficit this exercise addresses."
    )
    instructions: str = Field(
        description="Step-by-step instructions (2-4 sentences) for the patient."
    )
    frequency: str = Field(
        description="Recommended frequency, e.g. '3 sets of 10 repetitions, twice daily'."
    )


class ClinicalReport(BaseModel):
    """
    Structured clinical dysarthria screening report produced by NeuroClear.

    IMPORTANT: This report is ONLY populated with dysarthria-specific findings
    when objective evidence across multiple independent signal domains converges.
    A single anomalous metric is NEVER sufficient to flag dysarthria.
    """

    # ── Section 1: Intelligibility Analysis ─────────────────────────────────────
    transcript_accuracy_assessment: str = Field(
        description=(
            "A clinical paragraph comparing the TARGET text against the Whisper "
            "transcript. Identify any substitutions, omissions, or insertions. "
            "IMPORTANT: Whisper hallucination is a common technical artefact and "
            "must NOT be interpreted as a patient intelligibility failure unless "
            "other corroborating signals also show impairment."
        )
    )

    # ── Section 2: Phonetic / Articulation Analysis ────────────────────────────
    overall_articulation_quality: str = Field(
        description=(
            "An objective, measured assessment of articulation based solely on "
            "the CTC log-probability scores. Note that a single word with a low "
            "score may indicate background noise, microphone proximity, or a "
            "Whisper alignment error — not necessarily dysarthric articulation. "
            "Comment only on consistent patterns across multiple words."
        )
    )
    flagged_words: List[WordArticulationFlag] = Field(
        description=(
            "Words with CTC confidence below -1.5 that show a CONSISTENT pattern "
            "with other words (i.e., not isolated outliers). A single low-confidence "
            "word in isolation must not be flagged as dysarthric — it is likely a "
            "recording artefact. Return an empty list if no consistent pattern exists."
        )
    )

    # ── Section 3: Prosody Analysis ──────────────────────────────────────────────
    prosody_evaluation: str = Field(
        description=(
            "An objective evaluation of prosody. Reference specific WPM and gap "
            "values vs. healthy norms (130–180 WPM, avg gap < 0.3s). "
            "IMPORTANT: A slow speaking rate alone is NOT sufficient to conclude "
            "dysarthria. It may reflect deliberate reading pace, cognitive load, "
            "or nervousness. Flag prosody as clinically concerning ONLY when the "
            "rate is substantially below 80 WPM AND there are corroborating "
            "findings in other domains."
        )
    )
    max_silent_pause_note: str = Field(
        description=(
            "A sentence noting the maximum silent pause and its plausible "
            "explanations. Always consider non-pathological explanations "
            "(breath control, reading hesitation) alongside pathological ones "
            "(bradykinesia, word retrieval failure) before drawing conclusions."
        )
    )

    # ── Section 4: Motor Tremor & Disfluency Analysis ───────────────────────────
    motor_tremor_assessment: str = Field(
        description=(
            "A paragraph assessing motor tremor and disfluency events. "
            "The DSP peak detector can produce false positives due to background "
            "noise bursts, microphone handling, or lip-smacking in healthy speakers. "
            "Only treat these events as clinically significant if the "
            "active_tremor_time is substantial (> 0.5s) or events are recurrent "
            "across multiple words."
        )
    )
    detected_events: List[StutterEvent] = Field(
        description=(
            "Clinically significant stutter or false-start events only. "
            "Exclude events with active_tremor_time < 0.3s, as they are within "
            "normal disfluency range. Return an empty list if no events meet "
            "the clinical significance threshold."
        )
    )

    # ── Section 5: Dysarthria Detection Gate ──────────────────────────────────────
    dysarthria_detected: bool = Field(
        description=(
            "CRITICAL FIELD. Set to true when objective evidence of dysarthria "
            "is clearly present across at LEAST TWO independent signal domains "
            "(articulation, prosody, motor tremor), OR when a SINGLE domain shows "
            "severe, unambiguous impairment (e.g., WPM < 50, or a CTC score < -3.0 "
            "on multiple words). "
            "Set to false only when each flagged metric has a plausible "
            "non-pathological explanation (e.g., recording noise, deliberate "
            "reading pace) AND no other domain corroborates the finding. "
            "When in doubt and signals are genuinely borderline, set to false "
            "and use confidence_in_assessment = 'Low'."
        )
    )
    dysarthria_severity: Optional[str] = Field(
        default=None,
        description=(
            "ONLY populate if dysarthria_detected is true. "
            "Must be exactly one of: 'Mild', 'Mild-to-Moderate', 'Moderate', "
            "'Moderate-to-Severe', 'Severe'. "
            "Set to null if dysarthria_detected is false."
        )
    )
    severity_rationale: str = Field(
        description=(
            "If dysarthria_detected is true: one paragraph justifying the "
            "severity level by citing ≥2 specific metric values from different "
            "signal domains. "
            "If dysarthria_detected is false: a brief statement explaining "
            "why the evidence was insufficient to confirm dysarthria, noting "
            "which metrics appeared within normal limits."
        )
    )
    confidence_in_assessment: str = Field(
        description=(
            "The model's confidence in its detection decision. "
            "Must be exactly one of: 'High', 'Moderate', 'Low'. "
            "Use 'Low' whenever there is any ambiguity (e.g., borderline metrics, "
            "suspected recording artefacts, short audio sample). "
            "'High' requires strong, unambiguous evidence across all signal domains."
        )
    )

    # ── Section 6: Clinical Recommendations ────────────────────────────────────────
    primary_deficit_summary: str = Field(
        description=(
            "If dysarthria_detected is true: a single sentence naming the "
            "primary deficit (e.g., 'Hypokinetic dysarthria with bradylalia'). "
            "If dysarthria_detected is false: 'No dysarthria detected in this "
            "screening session. Recommend clinical follow-up if symptoms persist.'"
        )
    )
    recommended_exercises: List[SpeechExercise] = Field(
        description=(
            "If dysarthria_detected is true: 2-3 targeted speech exercises "
            "tailored to the SPECIFIC deficits observed in this session. "
            "If dysarthria_detected is false: return an empty list."
        )
    )
    follow_up_recommendation: str = Field(
        description=(
            "If dysarthria_detected is true: recommended frequency and focus "
            "of formal SLP follow-up based on severity. "
            "If dysarthria_detected is false: 'No immediate SLP referral "
            "indicated. Repeat screening if clinical symptoms are reported.'"
        )
    )

    # ── Section 7: Disclaimer ────────────────────────────────────────────────────────
    disclaimer: str = Field(
        description=(
            "Standard clinical disclaimer. Must be: "
            "'This automated assessment is generated by NeuroClear AI and is "
            "intended to assist, not replace, the clinical judgment of a "
            "qualified Speech-Language Pathologist.'"
        )
    )


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_prompt(
    target_text: str,
    patient_text: str,
    prosody_data: Dict[str, Any],
    articulation_data: List[Dict[str, Any]],
    tremor_data: List[Dict[str, Any]],
    false_start_data: List[Dict[str, Any]],
) -> str:
    """Construct the XML-structured clinical assessment prompt."""

    # Pre-process articulation data: identify low-confidence words (< -1.0)
    low_confidence = [
        w for w in articulation_data if w.get("confidence", 0.0) < -1.0
    ]

    return f"""\
<role>
You are an experienced Speech-Language Pathologist (SLP) conducting an \
objective automated dysarthria screening. Your goal is ACCURATE DETECTION — \
you must identify dysarthria when the evidence supports it, and clear the \
patient when it does not. Both false positives (over-diagnosis) and false \
negatives (missed diagnoses) cause patient harm. Apply balanced, \
evidence-based clinical judgment. Flag dysarthria when at least two independent \
signal domains show clear, measurable impairment.
</role>

<context>
The patient was given the following TARGET text to read aloud:
  "{target_text}"

The NeuroClear AI pipeline extracted the following objective metrics.
These are your ONLY source of evidence. Do not fabricate data.

<data id="stage1_transcription">
Actual patient transcript (from Whisper ASR):
  "{patient_text}"
Clinical note: Whisper may hallucinate or drop disfluent phonemes. A transcript
mismatch alone is not diagnostic. However, if articulation scores or tremor
events also indicate impairment, consider the mismatch as corroborating evidence.
</data>

<data id="stage2_articulation_confidence">
Per-word CTC log-probability scores from Wav2Vec2 forced alignment.
Scale: 0.0 = perfect articulation; more negative = worse clarity.
  - Score > -0.5              : Normal articulation
  - Score -0.5 to -1.0       : Mild degradation (may be noise, accent, or speed)
  - Score -1.0 to -2.0       : Moderate impairment — clinically notable
  - Score below -2.0          : Severe impairment — strong indicator of dysarthria
Interpretation guidance: An isolated single-word outlier may be a recording
artefact. However, a PATTERN across multiple words, OR a single extremely
low score (< -3.0), is a strong positive indicator.
{json.dumps(articulation_data, indent=2)}
</data>

<data id="stage4_prosody_metrics">
Speaking rate and pause analysis (false-start time already removed):
{json.dumps(prosody_data, indent=2)}
Healthy norms: 130–180 WPM; avg inter-word gap < 0.3s.
Clinical severity anchors for speaking rate:
  - 100-130 WPM (borderline): Low concern; may be deliberate reading pace.
  - 80-100 WPM (mild):        Clinically notable; consistent with mild dysarthria
                              if corroborated by other domain findings.
  - Below 80 WPM (moderate):  A strong, independent indicator of dysarthria.
                              Even with no other signals, below 80 WPM warrants
                              flagging as clinically significant.
  - Below 50 WPM (severe):    Almost always pathological.
For inter-word gaps, a max_gap > 1.0s or avg_gap > 0.5s is notable.
</data>

<data id="stage4_within_word_tremor">
Words flagged for within-word motor tremor. The DSP threshold is already
conservative: peaks must exceed syllable_count + 1.
Interpretation guidance:
  - A single flagged word with stutter_flag=true is a weak signal.
  - Two or more flagged words, OR one flagged word with low CTC confidence
    on the same word, is a strong positive indicator for motor disfluency.
{json.dumps(tremor_data, indent=2)}
</data>

<data id="stage4_false_starts">
Inter-word gap events with unexpected vocal energy (false starts / pre-voicing tremors).
Interpretation guidance:
  - active_tremor_time < 0.2s: Likely normal disfluency, low significance.
  - active_tremor_time 0.2–0.5s: Mild pre-voicing anomaly; corroborating signal.
  - active_tremor_time > 0.5s: Clinically significant motor struggle event.
  - Multiple flagged gaps: Strong indicator of motor control impairment.
{json.dumps(false_start_data, indent=2)}
</data>

<data id="low_confidence_words_summary">
Words with confidence below -1.0 (pre-filtered for clinical review):
{json.dumps(low_confidence, indent=2)}
</data>
</context>

<instructions>
1. Analyse ALL data sections systematically before reaching any conclusion.
2. Cite specific numeric values for every clinical claim.
3. Apply the TWO-DOMAIN RULE for dysarthria_detected:
   - Set to TRUE if clear, measurable impairment is present in at least TWO
     independent signal domains: [articulation, prosody, motor_tremor].
   - Exception: Set to TRUE for a single domain if the evidence is
     unambiguous and severe (e.g., WPM < 50, or a word with CTC < -3.0).
   - Set to FALSE only when the evidence in each domain is genuinely borderline
     or explicable by non-pathological factors.
4. Do NOT automatically dismiss a signal just because a confound is possible.
   Weigh the evidence; note the alternative explanation but reach a decision.
5. Do NOT infer across domains (e.g., do not infer articulation failure from
   slow WPM alone; treat each domain independently first).
6. dysarthria_severity must be null if dysarthria_detected is false.
7. recommended_exercises must be an empty list if dysarthria_detected is false.
8. The disclaimer field must contain the exact verbatim string specified.
9. confidence_in_assessment should reflect actual certainty:
   - 'High': Multiple domains show unambiguous impairment.
   - 'Moderate': Two domains show impairment but at least one is borderline.
   - 'Low': Only one domain shows impairment, or evidence is genuinely ambiguous.
</instructions>

<constraints>
- Tone: Formal, objective, clinically precise.
- Do not use patient names (anonymised data).
- Do not include any text outside the JSON structure.
- Each prose field: 2–4 sentences unless otherwise specified.
</constraints>

<task>
Based on the objective metrics provided, generate an accurate, balanced clinical \
screening report. Flag dysarthria when the evidence warrants it; clear the patient \
when it does not. Accuracy is the goal, not conservatism or permissiveness.
</task>
"""


# ── Public API ────────────────────────────────────────────────────────────────

def generate_clinical_report(
    target_text: str,
    patient_text: str,
    prosody_data: Dict[str, Any],
    articulation_data: List[Dict[str, Any]],
    tremor_data: List[Dict[str, Any]],
    false_start_data: Optional[List[Dict[str, Any]]] = None,
    cancellation_token: Optional[CancellationToken] = None,
) -> Dict[str, Any]:
    """Generate a structured LLM clinical report from NeuroClear pipeline metrics.

    Calls the Gemini API using the Interactions API with Pydantic-enforced JSON
    structured output.  Returns a plain dictionary safe for JSON serialisation.

    Parameters
    ----------
    target_text : str
        The reference sentence the patient was asked to read.
    patient_text : str
        The transcript produced by Whisper in Stage 1.
    prosody_data : dict
        Output of ``calculate_prosody_metrics`` (Stage 4a).
    articulation_data : list[dict]
        Per-word alignment list with ``word`` and ``confidence`` keys (Stage 2).
    tremor_data : list[dict]
        Output of ``detect_stutters`` (Stage 4d).
    false_start_data : list[dict], optional
        Output of ``detect_false_starts`` (Stage 4a).  Pass empty list if
        not available.

    Returns
    -------
    dict
        The structured clinical report, or a fallback error dict if the
        API call or JSON parsing fails.
    """
    false_start_data = false_start_data or []

    prompt = _build_prompt(
        target_text=target_text,
        patient_text=patient_text,
        prosody_data=prosody_data,
        articulation_data=articulation_data,
        tremor_data=tremor_data,
        false_start_data=false_start_data,
    )

    print(f"[llm_service] Sending clinical data to {_MODEL} …")

    if cancellation_token and cancellation_token.is_cancelled:
        print("[llm_service] Cancellation detected. Aborting Gemini API call.")
        raise Exception("Client disconnected before LLM call")

    try:
        interaction = _client.interactions.create(
            model=_MODEL,
            input=prompt,
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": ClinicalReport.model_json_schema(),
            },
        )

        raw_text: str = interaction.output_text or ""

        # ── CRITICAL SAFEGUARD: parse & validate ──────────────────────────
        try:
            report_dict = ClinicalReport.model_validate_json(raw_text).model_dump()
            print("[llm_service] Clinical report generated and validated successfully.")
            return report_dict

        except Exception as parse_err:
            print(
                f"[llm_service] WARNING: Pydantic validation failed: {parse_err}\n"
                "             Falling back to raw json.loads …"
            )
            # Last-resort: try raw JSON parse before giving up
            try:
                return json.loads(raw_text)
            except json.JSONDecodeError as je:
                print(f"[llm_service] ERROR: JSON decode failed: {je}")
                return {
                    "error": "JSON parsing failed",
                    "detail": str(je),
                    "raw_response": raw_text[:500],
                }

    except Exception as api_err:
        print(f"[llm_service] ERROR: Gemini API call failed: {api_err}")
        return {
            "error": "Gemini API call failed",
            "detail": str(api_err),
        }
