"use client";

import { useEffect, useState } from "react";
import { Mic, PlayCircle, Clock, ArrowRight, Target, FileText } from "lucide-react";
import Link from "next/link";

// ── TypeScript Interface ──────────────────────────────────────────────────
// This perfectly maps to the SpeechExercise Pydantic model in your backend
interface SpeechExercise {
  exercise_name: string;
  target_deficit: string;
  instructions: string;
  frequency: string;
}

export default function PracticePage() {
  const [exercises, setExercises] = useState<SpeechExercise[]>([]);
  const [isLoaded, setIsLoaded] = useState(false);

  // ── Hydration-Safe LocalStorage Read ────────────────────────────────────
  useEffect(() => {
    try {
      const stored = localStorage.getItem("neuroclear_exercises");
      if (stored) {
        setExercises(JSON.parse(stored));
      }
    } catch (error) {
      console.error("Failed to parse exercises from local storage", error);
    }
    // Mark as loaded so we can safely render the UI without hydration mismatches
    setIsLoaded(true);
  }, []);

  // ── Loading State ───────────────────────────────────────────────────────
  if (!isLoaded) {
    return (
      <div className="flex min-h-full items-center justify-center bg-gray-50 p-8">
        <p className="animate-pulse text-sm font-medium text-gray-500">
          Loading rehabilitation plan...
        </p>
      </div>
    );
  }

  return (
    <div className="min-h-full bg-gray-50 p-8">
      {/* ── Page Header ──────────────────────────────────────────────── */}
      <div className="mb-8 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-100">
          <Mic className="h-5 w-5 text-brand-700" />
        </div>
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-gray-900">
            Daily Practice
          </h1>
          <p className="text-sm text-gray-500">
            Personalized rehabilitation exercises based on your latest diagnosis
          </p>
        </div>
      </div>

      {/* ── Empty State (No Exercises Found) ─────────────────────────── */}
      {exercises.length === 0 ? (
        <div className="mt-12 flex max-w-lg flex-col items-center justify-center rounded-2xl border border-dashed border-gray-300 bg-white p-12 text-center shadow-sm">
          <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-gray-100">
            <FileText className="h-8 w-8 text-gray-400" />
          </div>
          <h2 className="mb-2 text-xl font-bold text-gray-900">
            No Active Prescriptions
          </h2>
          <p className="mb-8 text-sm leading-relaxed text-gray-500">
            You do not have any recommended exercises in your current session. Please complete a diagnostic screening to generate a personalized rehabilitation plan.
          </p>
          <Link
            href="/screening"
            className="inline-flex items-center gap-2 rounded-xl bg-brand-600 px-6 py-3 text-sm font-semibold text-white shadow-md shadow-brand-600/25 transition-all duration-200 hover:bg-brand-700 active:scale-95"
          >
            Go to Screening <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      ) : (
        /* ── Exercise Grid ─────────────────────────────────────────────── */
        <div className="grid max-w-5xl grid-cols-1 gap-6 lg:grid-cols-2">
          {exercises.map((exercise, idx) => (
            <div
              key={idx}
              className="flex flex-col justify-between rounded-2xl border border-gray-200 bg-white p-6 shadow-sm transition-all duration-200 hover:shadow-md"
            >
              <div>
                <div className="mb-4 flex items-start justify-between gap-4">
                  <h3 className="text-lg font-bold text-gray-900 leading-tight">
                    {exercise.exercise_name}
                  </h3>
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-blue-50">
                    <PlayCircle className="h-5 w-5 text-blue-600" />
                  </div>
                </div>

                <div className="mb-5 inline-flex items-center gap-1.5 rounded-lg border border-red-100 bg-red-50 px-3 py-1.5">
                  <Target className="h-3.5 w-3.5 text-red-600" />
                  <span className="text-xs font-semibold uppercase tracking-wider text-red-700">
                    Target: {exercise.target_deficit}
                  </span>
                </div>

                <p className="mb-6 text-sm leading-relaxed text-gray-600">
                  {exercise.instructions}
                </p>
              </div>

              <div className="flex items-center gap-2 rounded-xl bg-gray-50 p-3 border border-gray-100">
                <Clock className="h-4 w-4 text-gray-400" />
                <span className="text-xs font-medium text-gray-600">
                  Frequency: <span className="font-semibold text-gray-800">{exercise.frequency}</span>
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
