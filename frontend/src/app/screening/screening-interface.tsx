"use client";

import { useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Loader2,
  Mic,
  MicOff,
  Square,
} from "lucide-react";

// ── Types ──────────────────────────────────────────────────────────────────

type Status = "idle" | "recording" | "processing" | "complete";

// Exact pipeline phases, each with a start-offset in milliseconds
interface Phase {
  delayMs: number;
  text: string;
}

const PIPELINE_PHASES: Phase[] = [
  { delayMs: 0,     text: "Transcribing audio via Whisper ASR..." },
  { delayMs: 4000,  text: "Aligning phonetic timestamps..." },
  { delayMs: 8000,  text: "Extracting DSP motor tremor envelopes..." },
  { delayMs: 14000, text: "Generating Gemini clinical report..." },
];
const COMPLETION_DELAY_MS = 20_000;

// ── Component ──────────────────────────────────────────────────────────────

export default function ScreeningInterface({ passages }: { passages: string[] }) {
  const [targetText, setTargetText] = useState<string>("");
  const [status, setStatus]         = useState<Status>("idle");
  const [audioBlob, setAudioBlob]   = useState<Blob | null>(null);
  const [audioUrl, setAudioUrl]     = useState<string | null>(null);
  const [loadingText, setLoadingText] = useState<string>("");
  const [error, setError]           = useState<string | null>(null);

  // Refs persist across renders without triggering re-renders
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef        = useRef<Blob[]>([]);
  const streamRef        = useRef<MediaStream | null>(null);

  // ── Recording logic ────────────────────────────────────────────────────

  async function startRecording() {
    setError(null);
    chunksRef.current = [];

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e: BlobEvent) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };

      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        const url  = URL.createObjectURL(blob);
        setAudioBlob(blob);
        setAudioUrl(url);

        // Kill the red mic indicator in the browser immediately
        streamRef.current?.getTracks().forEach((t) => t.stop());

        setStatus("processing");
      };

      recorder.start();
      setStatus("recording");
    } catch (err) {
      const message =
        err instanceof DOMException && err.name === "NotAllowedError"
          ? "Microphone access was denied. Please allow microphone permissions and try again."
          : "Could not access your microphone. Please check your device settings.";
      setError(message);
    }
  }

  function stopRecording() {
    mediaRecorderRef.current?.stop();
    // onstop handler above will set status to "processing"
  }

  // ── Phased loading sequence ────────────────────────────────────────────

  useEffect(() => {
    if (status !== "processing") return;

    const timers: ReturnType<typeof setTimeout>[] = [];

    // Schedule each phase text update
    PIPELINE_PHASES.forEach(({ delayMs, text }) => {
      timers.push(setTimeout(() => setLoadingText(text), delayMs));
    });

    // Schedule completion
    timers.push(
      setTimeout(() => setStatus("complete"), COMPLETION_DELAY_MS)
    );

    // Cleanup: cancel all pending timers if component unmounts mid-pipeline
    return () => timers.forEach(clearTimeout);
  }, [status]);

  // ── Random sentence selection on mount ───────────────────────────────────

  useEffect(() => {
    // Pick a random sentence only once when the client mounts.
    // This avoids Server/Client hydration mismatch errors.
    const randomIndex = Math.floor(Math.random() * passages.length);
    setTargetText(passages[randomIndex]);
  }, [passages]);

  // ── Cleanup object URL on unmount to prevent memory leaks ─────────────

  useEffect(() => {
    return () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    };
  }, [audioUrl]);

  // ── Reset helper ───────────────────────────────────────────────────────

  function reset() {
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    setStatus("idle");
    setAudioBlob(null);
    setAudioUrl(null);
    setLoadingText("");
    setError(null);
    chunksRef.current = [];
  }

  // ── Render ─────────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col items-center gap-6">

      {/* ── Target sentence card ──────────────────────────────────────── */}
      <div className="w-full rounded-xl border border-blue-100 bg-blue-50 px-5 py-4 shadow-sm">
        <p className="mb-2 text-xs font-bold uppercase tracking-wider text-blue-600">
          Read this passage aloud
        </p>
        <p className="text-base font-medium leading-relaxed text-blue-950">
          {targetText ? `"${targetText}"` : "Loading passage..."}
        </p>
      </div>

      {/* ── Status card ─────────────────────────────────────────────────── */}
      <div className="relative w-full overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm">

        {/* Subtle top accent bar that changes colour by status */}
        <div
          className={`h-1 w-full transition-all duration-700 ${
            status === "idle"       ? "bg-gray-200"
            : status === "recording"  ? "animate-pulse bg-red-500"
            : status === "processing" ? "bg-brand-500"
            : /* complete */           "bg-emerald-500"
          }`}
        />

        <div className="flex flex-col items-center gap-6 px-8 py-10">

          {/* ── Idle ──────────────────────────────────────────────────── */}
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

          {/* ── Recording ─────────────────────────────────────────────── */}
          {status === "recording" && (
            <>
              {/* Pulsing red ring around mic icon */}
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
                  Speak clearly. Press stop when you are finished.
                </p>
              </div>
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
            </>
          )}

          {/* ── Processing ────────────────────────────────────────────── */}
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

              {/* Pipeline progress steps */}
              <div className="flex w-full max-w-xs flex-col gap-2">
                {PIPELINE_PHASES.map(({ text }) => {
                  const currentIndex = PIPELINE_PHASES.findIndex(
                    (p) => p.text === loadingText
                  );
                  const stepIndex = PIPELINE_PHASES.findIndex(
                    (p) => p.text === text
                  );
                  const done    = stepIndex < currentIndex;
                  const active  = stepIndex === currentIndex;

                  return (
                    <div key={text} className="flex items-center gap-3">
                      <div
                        className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[10px] font-bold transition-all duration-300 ${
                          done
                            ? "border-brand-500 bg-brand-500 text-white"
                            : active
                            ? "border-brand-500 bg-white text-brand-600"
                            : "border-gray-200 bg-gray-50 text-gray-400"
                        }`}
                      >
                        {done ? "✓" : stepIndex + 1}
                      </div>
                      <span
                        className={`text-xs transition-colors duration-300 ${
                          done
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

          {/* ── Complete ──────────────────────────────────────────────── */}
          {status === "complete" && (
            <>
              <div className="flex h-20 w-20 items-center justify-center rounded-full border-2 border-emerald-500 bg-emerald-50">
                <CheckCircle2 className="h-9 w-9 text-emerald-500" />
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

              {/* Audio playback — stretch goal */}
              {audioUrl && (
                <div className="w-full rounded-xl border border-gray-200 bg-gray-50 p-4">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
                    Session Recording
                  </p>
                  <audio
                    controls
                    src={audioUrl}
                    className="w-full rounded-lg"
                  />
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

        </div>
      </div>

      {/* ── Error banner ────────────────────────────────────────────────── */}
      {error && (
        <div className="flex w-full items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3">
          <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-500" />
          <div>
            <p className="text-sm font-semibold text-red-700">
              Microphone Error
            </p>
            <p className="mt-0.5 text-sm text-red-600">{error}</p>
          </div>
        </div>
      )}
    </div>
  );
}
