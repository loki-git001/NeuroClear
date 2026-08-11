import Link from "next/link";
import { ArrowRight, Brain, Activity, Mic, ShieldCheck, Waves } from "lucide-react";

export default function LandingPage() {
  return (
    <div className="min-h-full bg-white font-sans selection:bg-blue-100 selection:text-blue-900">
      
      {/* ── Navigation ─────────────────────────────────────────────────── */}
      <nav className="flex items-center justify-between border-b border-gray-100 px-8 py-5">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600">
            <Brain className="h-5 w-5 text-white" />
          </div>
          <span className="text-xl font-bold tracking-tight text-gray-900">
            NeuroClear
          </span>
        </div>
        <div className="flex items-center gap-4">
          <Link
            href="/screening"
            className="text-sm font-semibold text-gray-600 transition-colors hover:text-gray-900"
          >
            Clinical Dashboard
          </Link>
          <Link
            href="/screening"
            className="inline-flex items-center gap-2 rounded-xl bg-gray-900 px-4 py-2 text-sm font-semibold text-white transition-all hover:bg-gray-800 hover:shadow-md active:scale-95"
          >
            Run Screening <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      </nav>

      {/* ── Hero Section ───────────────────────────────────────────────── */}
      <main className="mx-auto max-w-5xl px-6 py-20 text-center md:py-32">
        <div className="mx-auto mb-6 inline-flex items-center gap-2 rounded-full border border-blue-100 bg-blue-50 px-4 py-1.5">
          <span className="flex h-2 w-2 rounded-full bg-blue-600 animate-pulse"></span>
          <span className="text-xs font-bold uppercase tracking-wider text-blue-700">
            Clinical Research Use Only
          </span>
        </div>
        
        <h1 className="mb-6 text-5xl font-extrabold tracking-tight text-gray-900 md:text-7xl">
          Automated Dysarthria <br className="hidden md:block" />
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-600">
            Speech Analysis
          </span>
        </h1>
        
        <p className="mx-auto mb-10 max-w-2xl text-lg leading-relaxed text-gray-500 md:text-xl">
          NeuroClear leverages state-of-the-art acoustic feature extraction and generative AI to provide objective, multi-domain motor speech assessments in seconds.
        </p>
        
        <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
          <Link
            href="/screening"
            className="inline-flex h-14 w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-8 text-base font-semibold text-white shadow-lg shadow-blue-600/25 transition-all hover:bg-blue-700 hover:shadow-xl hover:shadow-blue-600/30 active:scale-95 sm:w-auto"
          >
            Start Diagnostic Screening <ArrowRight className="h-5 w-5" />
          </Link>
          <Link
            href="/practice"
            className="inline-flex h-14 w-full items-center justify-center gap-2 rounded-xl border border-gray-200 bg-white px-8 text-base font-semibold text-gray-700 shadow-sm transition-all hover:border-gray-300 hover:bg-gray-50 active:scale-95 sm:w-auto"
          >
            <Mic className="h-5 w-5 text-gray-400" /> Patient Practice
          </Link>
        </div>
      </main>

      {/* ── Technical Architecture Section ─────────────────────────────── */}
      <section className="bg-gray-50 py-24 border-t border-gray-100">
        <div className="mx-auto max-w-5xl px-6">
          <div className="mb-16 text-center">
            <h2 className="text-3xl font-bold text-gray-900">
              Rigorous Machine Learning Pipeline
            </h2>
            <p className="mt-4 text-gray-500">
              Built on a decoupled architecture combining deep learning classifiers with digital signal processing.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-8 md:grid-cols-3">
            
            {/* Feature 1 */}
            <div className="rounded-2xl border border-gray-200 bg-white p-8 shadow-sm transition-all hover:shadow-md">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-50 border border-indigo-100">
                <Mic className="h-6 w-6 text-indigo-600" />
              </div>
              <h3 className="mb-3 text-lg font-bold text-gray-900">
                Phonetic Alignment
              </h3>
              <p className="text-sm leading-relaxed text-gray-500">
                Utilizes Wav2Vec2 Connectionist Temporal Classification (CTC) to extract log-probability confidence scores, identifying micro-articulatory decay at the phoneme level.
              </p>
            </div>

            {/* Feature 2 */}
            <div className="rounded-2xl border border-gray-200 bg-white p-8 shadow-sm transition-all hover:shadow-md">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-amber-50 border border-amber-100">
                <Waves className="h-6 w-6 text-amber-600" />
              </div>
              <h3 className="mb-3 text-lg font-bold text-gray-900">
                DSP Tremor Detection
              </h3>
              <p className="text-sm leading-relaxed text-gray-500">
                SciPy-driven amplitude envelope extraction. Our peak-finding algorithms isolate involuntary motor tremors and false-starts independent of language context.
              </p>
            </div>

            {/* Feature 3 */}
            <div className="rounded-2xl border border-gray-200 bg-white p-8 shadow-sm transition-all hover:shadow-md">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-50 border border-emerald-100">
                <Activity className="h-6 w-6 text-emerald-600" />
              </div>
              <h3 className="mb-3 text-lg font-bold text-gray-900">
                LLM Clinical Synthesis
              </h3>
              <p className="text-sm leading-relaxed text-gray-500">
                Passes objective prosody and regression metrics into a strictly constrained Gemini schema to output reliable, structured clinical diagnostic rationales.
              </p>
            </div>

          </div>
        </div>
      </section>

      {/* ── Footer ─────────────────────────────────────────────────────── */}
      <footer className="border-t border-gray-100 bg-white py-8 text-center">
        <div className="flex items-center justify-center gap-2 text-sm text-gray-400">
          <ShieldCheck className="h-4 w-4" />
          <span>NeuroClear v1.0.0 — Hackathon MVP</span>
        </div>
      </footer>
      
    </div>
  );
}