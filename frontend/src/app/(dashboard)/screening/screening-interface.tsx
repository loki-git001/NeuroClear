"use client";

import { useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  Mic,
  MicOff,
  RefreshCw,
  Square,
  ClipboardList,
  XCircle,
} from "lucide-react";
import ClinicalDashboard from "./clinical-dashboard";

// ── Types ───────────────────────────────────────────────────────────────────

type Status = "idle" | "recording" | "processing" | "complete" | "error";

interface ClinicalReport {
  transcript_accuracy_assessment: string;
  overall_articulation_quality: string;
  flagged_words: {
    word: string;
    ctc_confidence: number;
    clinical_interpretation: string;
  }[];
  prosody_evaluation: string;
  max_silent_pause_note: string;
  motor_tremor_assessment: string;
  detected_events: {
    event_type: string;
    target_word: string;
    clinical_note: string;
  }[];
  dysarthria_detected: boolean;
  dysarthria_severity?: string | null;
  severity_rationale: string;
  confidence_in_assessment: string;
  primary_deficit_summary: string;
  disclaimer: string;
  recommended_exercises: string[];
}

// Pipeline phases — text advances via timeouts, but completion is gated
// entirely on the real network response resolving. No hard 20s cutoff.
interface Phase {
  delayMs: number;
  text: string;
}

const PIPELINE_PHASES: Phase[] = [
  { delayMs: 0, text: "Transcribing audio via Whisper ASR..." },
  { delayMs: 4000, text: "Aligning phonetic timestamps..." },
  { delayMs: 8000, text: "Extracting DSP motor tremor envelopes..." },
  { delayMs: 14000, text: "Generating Gemini clinical report..." },
];

// Next.js injects environment variables prefixed with NEXT_PUBLIC_ into the browser bundle.
// If the variable is missing (e.g., in a local test), it safely falls back to localhost.
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/analyze";
const MOCK_API = false; // Set to false to hit the real FastAPI backend

// ── Network layer ───────────────────────────────────────────────────────────

async function analyzeAudio(
  blob: Blob,
  text: string,
  signal: AbortSignal
): Promise<ClinicalReport> {
  if (MOCK_API) {
    return new Promise((resolve) => {
      setTimeout(() => {
        resolve({
          transcript_accuracy_assessment: "The Whisper ASR transcript reveals significant deviations from the TARGET text, including the substitution of 'ninety-three' with '90 to 3' and 'years old' with 'years of', followed by an extensive repetitive hallucination of 'E.E.S.T.' tokens at the transcript boundary. While automated transcription hallucination is a recognized technical artefact, the contextual breakdown in transcription coincides directly with severe speech slowing and extended pauses. Thus, the transcript mismatch serves as secondary corroboration of impaired speech flow.",
          overall_articulation_quality: "For the majority of the speech sample, phonetic articulation is well-maintained, with CTC log-probability scores ranging from -0.006 to -0.538 across most lexical items. However, noticeable articulatory degradation occurs at word-final positions, specifically on 'OLD' (-1.814) and 'EVER' (-1.962). This pattern indicates preserved central phonetic precision with mild-to-moderate terminal precision decay.",
          flagged_words: [
            {
              word: "OLD",
              ctc_confidence: -1.814,
              clinical_interpretation: "Moderate articulation score reduction indicating terminal word blurring or reduced vocal intensity at the end of the phrase."
            },
            {
              word: "EVER",
              ctc_confidence: -1.962,
              clinical_interpretation: "Moderate articulation score reduction reflecting acoustic decay and imprecise consonant release during final word production."
            }
          ],
          prosody_evaluation: "Prosodic analysis reveals severe impairment in speaking velocity and rhythmic flow. The patient demonstrated a speaking rate of 49.3 WPM, which falls substantially below healthy adult norms (130–180 WPM) and below the severe pathological threshold of 50 WPM. Additionally, inter-word silent gaps averaged 0.572s (normal < 0.3s) with 9 distinct pause events exceeding 0.5s, indicating severe bradylalia and marked speech initiation delays.",
          max_silent_pause_note: "The maximum silent gap measured 2.26s between 'NEARLY' and 'NINETYTHREE', likely reflecting motor hesitation, respiratory re-planning, or bradykinesia during complex numerical lexical retrieval.",
          motor_tremor_assessment: "The digital signal processing pipeline detected a prominent motor disfluency event during the production of the word 'WELL'. The token was abnormally prolonged to 3.66s and exhibited 12 distinct acoustic intensity peaks against an allowed threshold of 2 peaks, triggering a positive stutter/tremor flag. This recurrent amplitude fluctuation is consistent with active articulatory tremor or tonic motor blockage.",
          detected_events: [
            {
              event_type: "within_word_tremor",
              target_word: "WELL",
              clinical_note: "Severe acoustic energy fluctuation and vocal prolongation (3.66s, 12 peaks vs. 2 allowed) consistent with articulatory tremor or motor block."
            }
          ],
          dysarthria_detected: true,
          dysarthria_severity: "Moderate",
          severity_rationale: "Dysarthria is confirmed across multiple independent signal domains. Prosody exhibits severe impairment with a speaking rate of 49.3 WPM (< 50 WPM threshold) and 9 inter-word pauses over 0.5s (max gap 2.26s). Motor execution is concurrently impaired, demonstrated by a 3.66s within-word tremor event on 'WELL' with 12 acoustic peaks. Articulation further corroborates these findings with moderate terminal score drops on 'OLD' (-1.814) and 'EVER' (-1.962).",
          confidence_in_assessment: "High",
          primary_deficit_summary: "Dysarthria characterized by severe bradylalia, prominent inter-word silent hesitations, and localized motor disfluency/tremor.",
          recommended_exercises: [
            {
              exercise_name: "Rhythmic Pacing Board Drills",
              target_deficit: "Severe bradylalia and irregular inter-word silent pauses.",
              instructions: "Tap a finger on a table or pacing board for each syllable while reading aloud to establish a steady, rhythmic speech cadence. Focus on maintaining continuous air support between words to reduce prolonged gaps.",
              frequency: "3 sets of 5 sentence repetitions, twice daily."
            },
            {
              exercise_name: "Terminal Consonant Precision & Voicing Drills",
              target_deficit: "Articulatory decay on word-final phonemes (e.g., 'OLD', 'EVER').",
              instructions: "Read word pairs ending in voiced and voiceless stops, deliberately over-articulating the final consonant sounds. Maintain steady subglottal pressure until the final sound is fully released.",
              frequency: "2 sets of 10 word pairs, twice daily."
            }
          ],
          disclaimer: "This automated assessment is generated by NeuroClear AI and is intended to assist, not replace, the clinical judgment of a qualified Speech-Language Pathologist."
        } as unknown as ClinicalReport);
      }, 2500); // 2.5 second delay
    });
  }

  const formData = new FormData();
  formData.append("target_text", text);
  // FastAPI requires a filename to correctly interpret the file field
  formData.append("audio_file", blob, "session.webm");

  const response = await fetch(API_URL, {
    method: "POST",
    headers: {
      "ngrok-skip-browser-warning": "true",
    },
    body: formData,
    signal, // AbortController signal for race-condition safety on unmount
  });

  if (!response.ok) {
    // Try to read the backend's error detail; fall back to a generic message
    let detail = `Server error ${response.status}`;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // response body was not JSON — use the status text
      detail = response.statusText || detail;
    }
    throw new Error(detail);
  }

  return response.json() as Promise<ClinicalReport>;
}

// ── Component ───────────────────────────────────────────────────────────────

export default function ScreeningInterface({ passages }: { passages: string[] }) {
  const [targetText, setTargetText] = useState<string>("");
  const [status, setStatus] = useState<Status>("idle");
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [loadingText, setLoadingText] = useState<string>("");
  const [resultData, setResultData] = useState<ClinicalReport | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Mic-error is kept separate from the pipeline error state so the inline
  // banner and the full error-card don't clobber each other
  const [micError, setMicError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const maxRecordingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // AbortController lets us cancel the fetch if the component unmounts
  const abortControllerRef = useRef<AbortController | null>(null);

  // ── Restoration & Random sentence selection on mount ──────────────────────

  useEffect(() => {
    try {
      const storedReport = localStorage.getItem("neuroclear_latest_report");
      const storedTarget = localStorage.getItem("neuroclear_latest_target");
      if (storedReport) {
        setResultData(JSON.parse(storedReport));
        setStatus("complete");
        if (storedTarget) setTargetText(storedTarget);
        return; // Skip random passage selection if we restored a report
      }
    } catch {
      // JSON parse failed, fallback to random
    }

    const randomIndex = Math.floor(Math.random() * passages.length);
    setTargetText(passages[randomIndex]);
  }, [passages]);

  // ── Cleanup object URL on unmount / change ───────────────────────────────

  useEffect(() => {
    return () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    };
  }, [audioUrl]);

  // ── Abort any in-flight fetch on unmount ─────────────────────────────────

  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  // ── Recording ────────────────────────────────────────────────────────────

  async function startRecording() {
    setMicError(null);
    setErrorMessage(null);
    chunksRef.current = [];

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e: BlobEvent) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        const url = URL.createObjectURL(blob);
        setAudioBlob(blob);
        setAudioUrl(url);

        // Release the browser's red microphone indicator immediately
        streamRef.current?.getTracks().forEach((t) => t.stop());

        setStatus("processing");
      };

      recorder.start();
      setStatus("recording");

      // Start the 60-second safety cutoff
      maxRecordingTimerRef.current = setTimeout(() => {
        // console.log("60-second max limit reached. Auto-stopping...");
        stopRecording();
      }, 60000);
    } catch (err) {
      const message =
        err instanceof DOMException && err.name === "NotAllowedError"
          ? "Microphone access was denied. Please allow microphone permissions and try again."
          : "Could not access your microphone. Please check your device settings.";
      setMicError(message);
    }
  }

  function stopRecording() {
    if (maxRecordingTimerRef.current) {
      clearTimeout(maxRecordingTimerRef.current);
    }
    mediaRecorderRef.current?.stop();
    // onstop fires → blob is ready → status becomes "processing"
  }

  function cancelRecording() {
    // Clear the 60-second safety timer
    if (maxRecordingTimerRef.current) {
      clearTimeout(maxRecordingTimerRef.current);
    }
    // Suppress onstop from triggering the analysis pipeline
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.onstop = null;
      mediaRecorderRef.current.stop();
    }
    // Kill the microphone red indicator in the browser
    streamRef.current?.getTracks().forEach((t) => t.stop());
    // Discard any chunks recorded so far
    chunksRef.current = [];
    // Return to idle — user can start a fresh recording
    setStatus("idle");
  }

  // ── Phased loading text + real network call ───────────────────────────────
  //
  // When status becomes "processing" we:
  //   1. Schedule the phase-text animations (no forced completion timeout).
  //   2. Fire the real fetch with an AbortController for unmount safety.
  //   3. On success  → set resultData + "complete".
  //   4. On error    → set errorMessage + "error".

  useEffect(() => {
    if (status !== "processing") return;
    if (!audioBlob || !targetText) return;

    // ── Phase text timers (no completion timer — that's the network's job) ──
    const timers: ReturnType<typeof setTimeout>[] = [];
    PIPELINE_PHASES.forEach(({ delayMs, text }) => {
      timers.push(setTimeout(() => setLoadingText(text), delayMs));
    });

    // ── Real fetch ──────────────────────────────────────────────────────────
    const controller = new AbortController();
    abortControllerRef.current = controller;

    analyzeAudio(audioBlob, targetText, controller.signal)
      .then((data: ClinicalReport) => {
        // Log the raw payload for debugging
        // console.log("Gemini Output:", data);

        // Cache the exercises and the full report in localStorage for persistence
        try {
          localStorage.setItem(
            "neuroclear_exercises",
            JSON.stringify(data.recommended_exercises ?? [])
          );
          localStorage.setItem(
            "neuroclear_latest_report",
            JSON.stringify(data)
          );
          localStorage.setItem("neuroclear_latest_target", targetText);
        } catch {
          // localStorage unavailable in some environments — non-fatal
        }

        setResultData(data);
        setStatus("complete");
      })
      .catch((err: unknown) => {
        // Ignore errors from intentional AbortController cancellation
        if (err instanceof DOMException && err.name === "AbortError") return;

        const message =
          err instanceof Error
            ? err.message
            : "An unexpected error occurred during analysis.";
        setErrorMessage(message);
        setStatus("error");
      });

    return () => {
      timers.forEach(clearTimeout);
      controller.abort(); // cancel the fetch if status changes before it resolves
    };
  }, [status, audioBlob, targetText]);

  // ── Reset ─────────────────────────────────────────────────────────────────

  function reset() {
    abortControllerRef.current?.abort();
    if (audioUrl) URL.revokeObjectURL(audioUrl);

    try {
      localStorage.removeItem("neuroclear_latest_report");
      localStorage.removeItem("neuroclear_latest_target");
      localStorage.removeItem("neuroclear_exercises");
    } catch { }

    setStatus("idle");
    setAudioBlob(null);
    setAudioUrl(null);
    setLoadingText("");
    setResultData(null);
    setErrorMessage(null);
    setMicError(null);
    chunksRef.current = [];

    // Pick a new passage for the next session
    const randomIndex = Math.floor(Math.random() * passages.length);
    setTargetText(passages[randomIndex]);
  }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="flex w-full flex-col items-center gap-6">

      {/* ── Target sentence card ───────────────────────────────────────────── */}
      <div className="w-full max-w-lg rounded-xl border border-blue-100 bg-blue-50 px-5 py-4 shadow-sm">
        <p className="mb-2 text-xs font-bold uppercase tracking-wider text-blue-600">
          Read this passage aloud
        </p>
        <p className="text-base font-medium leading-relaxed text-blue-950">
          {targetText ? `"${targetText}"` : "Loading passage..."}
        </p>
      </div>

      {/* ── Status card ───────────────────────────────────────────────────── */}
      <div className="relative w-full max-w-lg overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">

        {/* Top accent bar — colour tracks status */}
        <div
          className={`h-1 w-full transition-all duration-700 ${status === "idle"
            ? "bg-gray-200"
            : status === "recording"
              ? "animate-pulse bg-red-500"
              : status === "processing"
                ? "bg-brand-500"
                : status === "complete"
                  ? "bg-emerald-500"
                  : /* error */ "bg-amber-500"
            }`}
        />

        <div className="flex flex-col items-center gap-6 px-8 py-10">

          {/* ── Idle ──────────────────────────────────────────────────────── */}
          {status === "idle" && (
            <>
              <div className="flex h-20 w-20 items-center justify-center rounded-full border-2 border-gray-200 bg-gray-50">
                <Mic className="h-8 w-8 text-gray-400" />
              </div>
              <div className="text-center">
                <p className="text-lg font-semibold text-gray-800">
                  Ready to record
                </p>
                <p className="mt-1 text-sm text-gray-500">
                  Press the button below, then read the target sentence aloud.
                </p>
              </div>
              <button
                onClick={startRecording}
                className="
                  inline-flex items-center gap-2 rounded-xl bg-brand-600
                  px-6 py-3 text-sm font-semibold text-white shadow-md
                  shadow-brand-600/25 transition-all duration-200
                  hover:bg-brand-700 hover:shadow-lg hover:shadow-brand-600/30
                  active:scale-95
                "
              >
                <Mic className="h-4 w-4" />
                Start Recording
              </button>
            </>
          )}

          {/* ── Recording ─────────────────────────────────────────────────── */}
          {status === "recording" && (
            <>
              <div className="relative flex h-20 w-20 items-center justify-center">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-30" />
                <div className="relative flex h-20 w-20 items-center justify-center rounded-full border-2 border-red-500 bg-red-50">
                  <Mic className="h-8 w-8 text-red-500" />
                </div>
              </div>
              <div className="text-center">
                <p className="text-lg font-semibold text-red-600">
                  Recording…
                </p>
                <p className="mt-1 text-sm text-gray-500">
                  Speak clearly. Auto-stops after 60 seconds.
                </p>
              </div>
              <div className="flex gap-3">
                <button
                  onClick={stopRecording}
                  className="
                    inline-flex items-center gap-2 rounded-xl bg-red-600
                    px-6 py-3 text-sm font-semibold text-white shadow-md
                    shadow-red-600/25 transition-all duration-200
                    hover:bg-red-700 active:scale-95
                  "
                >
                  <Square className="h-4 w-4 fill-white" />
                  Stop &amp; Analyze
                </button>

                <button
                  onClick={cancelRecording}
                  className="
                    inline-flex items-center gap-2 rounded-xl border border-gray-200
                    bg-white px-6 py-3 text-sm font-semibold text-gray-700
                    shadow-sm transition-all duration-200
                    hover:border-gray-300 hover:bg-gray-50 active:scale-95
                  "
                >
                  <XCircle className="h-4 w-4" />
                  Cancel
                </button>
              </div>
            </>
          )}

          {/* ── Processing ────────────────────────────────────────────────── */}
          {status === "processing" && (
            <>
              <div className="flex h-20 w-20 items-center justify-center rounded-full border-2 border-brand-200 bg-brand-50">
                <Loader2 className="h-8 w-8 animate-spin text-brand-600" />
              </div>
              <div className="text-center">
                <p className="text-lg font-semibold text-gray-800">
                  Analyzing your speech
                </p>
                <p className="mt-2 min-h-[20px] text-sm font-medium text-brand-600 transition-all duration-500">
                  {loadingText}
                </p>
              </div>

              {/* Live pipeline checklist */}
              <div className="flex w-full max-w-xs flex-col gap-2">
                {PIPELINE_PHASES.map(({ text }) => {
                  const currentIndex = PIPELINE_PHASES.findIndex(
                    (p) => p.text === loadingText
                  );
                  const stepIndex = PIPELINE_PHASES.findIndex(
                    (p) => p.text === text
                  );
                  const done = stepIndex < currentIndex;
                  const active = stepIndex === currentIndex;

                  return (
                    <div key={text} className="flex items-center gap-3">
                      <div
                        className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[10px] font-bold transition-all duration-300 ${done
                          ? "border-brand-500 bg-brand-500 text-white"
                          : active
                            ? "border-brand-500 bg-white text-brand-600"
                            : "border-gray-200 bg-gray-50 text-gray-400"
                          }`}
                      >
                        {done ? "✓" : stepIndex + 1}
                      </div>
                      <span
                        className={`text-xs transition-colors duration-300 ${done
                          ? "text-brand-600 line-through opacity-60"
                          : active
                            ? "font-semibold text-gray-800"
                            : "text-gray-400"
                          }`}
                      >
                        {text}
                      </span>
                    </div>
                  );
                })}
              </div>
            </>
          )}

          {/* ── Complete ──────────────────────────────────────────────────── */}
          {status === "complete" && resultData && (
            <>
              <div className={`flex h-20 w-20 items-center justify-center rounded-full border-2 ${resultData.dysarthria_detected
                ? "border-blue-500 bg-blue-50"
                : "border-emerald-500 bg-emerald-50"
                }`}>
                {resultData.dysarthria_detected ? (
                  <ClipboardList className="h-9 w-9 text-blue-500" />
                ) : (
                  <CheckCircle2 className="h-9 w-9 text-emerald-500" />
                )}
              </div>
              <div className="text-center">
                <p className="text-lg font-semibold text-gray-800">
                  Analysis Complete
                </p>
                <p className="mt-1 text-sm text-gray-500">
                  Your clinical report is ready. Navigate to{" "}
                  <span className="font-medium text-brand-600">
                    Diagnostic Report
                  </span>{" "}
                  to review the results.
                </p>
              </div>

              {/* Quick result summary if we have the data */}
              {resultData && (
                <div
                  className={`w-full rounded-xl border px-4 py-3 ${resultData.dysarthria_detected
                    ? "border-red-200 bg-red-50"
                    : "border-emerald-100 bg-emerald-50"
                    }`}
                >
                  <p
                    className={`text-xs font-semibold uppercase tracking-wider ${resultData.dysarthria_detected ? "text-red-700" : "text-emerald-700"
                      }`}
                  >
                    Dysarthria detected:{" "}
                    <span
                      className={
                        resultData.dysarthria_detected
                          ? "text-red-600"
                          : "text-emerald-600"
                      }
                    >
                      {resultData.dysarthria_detected ? "Yes" : "No"}
                    </span>
                  </p>
                  {resultData.dysarthria_severity && (
                    <p
                      className={`mt-0.5 text-xs ${resultData.dysarthria_detected ? "text-red-700" : "text-emerald-700"
                        }`}
                    >
                      Severity: <span className="font-medium">{resultData.dysarthria_severity}</span>
                    </p>
                  )}
                </div>
              )}

              {/* Audio playback */}
              {audioUrl && (
                <div className="w-full rounded-xl border border-gray-200 bg-gray-50 p-4">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
                    Session Recording
                  </p>
                  <audio controls src={audioUrl} className="w-full rounded-lg" />
                  <p className="mt-2 text-[11px] text-gray-400">
                    {audioBlob
                      ? `File size: ${(audioBlob.size / 1024).toFixed(1)} KB`
                      : null}
                  </p>
                </div>
              )}

              <button
                onClick={reset}
                className="
                  inline-flex items-center gap-2 rounded-xl border border-gray-200
                  bg-white px-6 py-3 text-sm font-semibold text-gray-700
                  shadow-sm transition-all duration-200 hover:border-gray-300
                  hover:bg-gray-50 active:scale-95
                "
              >
                <MicOff className="h-4 w-4" />
                Record New Session
              </button>
            </>
          )}

          {/* ── Error (pipeline / network failure) ───────────────────────── */}
          {status === "error" && (
            <>
              <div className="flex h-20 w-20 items-center justify-center rounded-full border-2 border-amber-400 bg-amber-50">
                <AlertTriangle className="h-9 w-9 text-amber-500" />
              </div>
              <div className="text-center">
                <p className="text-lg font-semibold text-gray-800">
                  Analysis Failed
                </p>
                <p className="mt-1 text-sm text-gray-500">
                  The pipeline could not complete your session.
                </p>
              </div>

              {/* Error detail card */}
              <div className="w-full rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
                  <div>
                    <p className="text-xs font-semibold text-amber-800">
                      Backend Error
                    </p>
                    <p className="mt-0.5 text-xs text-amber-700">
                      {errorMessage ?? "An unexpected error occurred."}
                    </p>
                  </div>
                </div>
              </div>

              <div className="flex gap-3">
                {/* Retry — reuses the existing blob + text, re-fires the fetch */}
                <button
                  onClick={() => {
                    setErrorMessage(null);
                    setStatus("processing");
                  }}
                  className="
                    inline-flex items-center gap-2 rounded-xl bg-brand-600
                    px-5 py-2.5 text-sm font-semibold text-white shadow-md
                    shadow-brand-600/25 transition-all duration-200
                    hover:bg-brand-700 active:scale-95
                  "
                >
                  <RefreshCw className="h-4 w-4" />
                  Retry Analysis
                </button>

                {/* Full reset — starts a completely new session */}
                <button
                  onClick={reset}
                  className="
                    inline-flex items-center gap-2 rounded-xl border border-gray-200
                    bg-white px-5 py-2.5 text-sm font-semibold text-gray-700
                    shadow-sm transition-all duration-200 hover:border-gray-300
                    hover:bg-gray-50 active:scale-95
                  "
                >
                  <MicOff className="h-4 w-4" />
                  New Session
                </button>
              </div>
            </>
          )}

        </div>
      </div>

      {/* ── MOUNT THE NEW CLINICAL DASHBOARD HERE (OUTSIDE THE STATUS CARD) ── */}
      {status === "complete" && resultData && (
        <ClinicalDashboard report={resultData} />
      )}
      {/* ─────────────────────────────────────────────────────────────────── */}

      {/* ── Microphone permission error banner (only shown in idle) ─────────── */}
      {micError && (
        <div className="flex w-full items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3">
          <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-500" />
          <div>
            <p className="text-sm font-semibold text-red-700">
              Microphone Error
            </p>
            <p className="mt-0.5 text-sm text-red-600">{micError}</p>
          </div>
        </div>
      )}
    </div>
  );
}