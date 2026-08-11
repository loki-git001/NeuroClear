import { Activity, Brain, Info, Mic, ShieldAlert, Waves } from "lucide-react";

// ── TypeScript Interfaces mapping to Python Backend ──────────────────────

interface WordArticulationFlag {
  word: string;
  ctc_confidence: number;
  clinical_interpretation: string;
}

interface StutterEvent {
  event_type: string;
  target_word: string;
  clinical_note: string;
}

// We omit the recommended_exercises here since they go to the Practice page
interface ClinicalReportProps {
  report: {
    transcript_accuracy_assessment: string;
    overall_articulation_quality: string;
    flagged_words: WordArticulationFlag[];
    prosody_evaluation: string;
    max_silent_pause_note: string;
    motor_tremor_assessment: string;
    detected_events: StutterEvent[];
    dysarthria_detected: boolean;
    dysarthria_severity?: string | null;
    severity_rationale: string;
    confidence_in_assessment: string;
    primary_deficit_summary: string;
    disclaimer: string;
  };
}

export default function ClinicalDashboard({ report }: ClinicalReportProps) {
  return (
    <div className="mt-8 flex w-full flex-col gap-6 animate-in fade-in slide-in-from-bottom-4 duration-700">
      
      {/* ── 1. Executive Summary & Rationale ───────────────────────────────── */}
      <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <div className="mb-4 flex items-center gap-2 border-b border-gray-100 pb-4">
          <Brain className="h-5 w-5 text-brand-600" />
          <h2 className="text-lg font-bold text-gray-900">AI Diagnostic Rationale</h2>
          <span className="ml-auto rounded-full bg-gray-100 px-3 py-1 text-[10px] font-bold uppercase tracking-widest text-gray-600">
            Confidence: {report.confidence_in_assessment}
          </span>
        </div>
        <p className="mb-4 text-sm font-semibold text-gray-800">
          {report.primary_deficit_summary}
        </p>
        <p className="text-sm leading-relaxed text-gray-600">
          {report.severity_rationale}
        </p>
        
        <div className="mt-6 rounded-lg bg-gray-50 p-4 border border-gray-100">
          <h3 className="mb-1 text-xs font-bold uppercase tracking-wider text-gray-500">
            Transcription Accuracy (Whisper ASR)
          </h3>
          <p className="text-sm text-gray-600">{report.transcript_accuracy_assessment}</p>
        </div>
      </div>

      {/* ── 2. Two-Column Grid: Articulation & Prosody ─────────────────────── */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        
        {/* Articulation Column */}
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
          <div className="mb-4 flex items-center gap-2 border-b border-gray-100 pb-4">
            <Mic className="h-5 w-5 text-brand-600" />
            <h2 className="text-base font-bold text-gray-900">Articulation Analysis</h2>
          </div>
          <p className="mb-5 text-sm text-gray-600">
            {report.overall_articulation_quality}
          </p>
          
          <h3 className="mb-3 text-xs font-bold uppercase tracking-wider text-gray-500">
            Flagged Phonetics (CTC Alignment)
          </h3>
          {report.flagged_words?.length > 0 ? (
            <div className="flex flex-col gap-3">
              {report.flagged_words.map((flag, idx) => (
                <div key={idx} className="rounded-lg border border-red-100 bg-red-50 p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-bold text-red-900">"{flag.word}"</span>
                    <span className="text-xs font-mono font-semibold text-red-600">
                      Score: {flag.ctc_confidence.toFixed(2)}
                    </span>
                  </div>
                  <p className="text-xs text-red-700">{flag.clinical_interpretation}</p>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex items-center gap-2 rounded-lg bg-emerald-50 p-3 border border-emerald-100 text-emerald-700">
              <Activity className="h-4 w-4" />
              <span className="text-xs font-medium">No severe articulatory breakdown detected.</span>
            </div>
          )}
        </div>

        {/* Prosody Column */}
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
          <div className="mb-4 flex items-center gap-2 border-b border-gray-100 pb-4">
            <Waves className="h-5 w-5 text-brand-600" />
            <h2 className="text-base font-bold text-gray-900">Prosody &amp; Pacing</h2>
          </div>
          <p className="mb-4 text-sm text-gray-600">
            {report.prosody_evaluation}
          </p>
          <div className="rounded-lg bg-blue-50 p-4 border border-blue-100">
            <div className="flex items-start gap-2">
              <Info className="mt-0.5 h-4 w-4 shrink-0 text-blue-600" />
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-blue-800">
                  Respiration &amp; Pauses
                </h3>
                <p className="mt-1 text-xs text-blue-900 leading-relaxed">
                  {report.max_silent_pause_note}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── 3. Motor Tremor & Disfluency ────────────────────────────────────── */}
      <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
        <div className="mb-4 flex items-center gap-2 border-b border-gray-100 pb-4">
          <Activity className="h-5 w-5 text-brand-600" />
          <h2 className="text-base font-bold text-gray-900">Motor Tremor &amp; Envelope DSP</h2>
        </div>
        <p className="mb-5 text-sm text-gray-600">
          {report.motor_tremor_assessment}
        </p>

        {report.detected_events?.length > 0 ? (
          <div className="overflow-hidden rounded-xl border border-gray-200">
            <table className="w-full text-left text-sm">
              <thead className="bg-gray-50 border-b border-gray-200 text-xs font-bold uppercase tracking-wider text-gray-500">
                <tr>
                  <th className="px-4 py-3">Event Type</th>
                  <th className="px-4 py-3">Target Word</th>
                  <th className="px-4 py-3">Clinical Note</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white">
                {report.detected_events.map((event, idx) => (
                  <tr key={idx}>
                    <td className="px-4 py-3 font-medium text-amber-700 capitalize">
                      {event.event_type.replace(/_/g, ' ')}
                    </td>
                    <td className="px-4 py-3 font-mono font-semibold text-gray-900">
                      "{event.target_word}"
                    </td>
                    <td className="px-4 py-3 text-gray-600 text-xs">
                      {event.clinical_note}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="flex items-center gap-2 rounded-lg bg-emerald-50 p-4 border border-emerald-100 text-emerald-700">
            <Activity className="h-4 w-4" />
            <span className="text-sm font-medium">No clinically significant motor tremor events detected in DSP envelope.</span>
          </div>
        )}
      </div>

      {/* ── 4. Medical Disclaimer ────────────────────────────────────────────── */}
      <div className="flex items-start gap-3 rounded-xl bg-gray-100 p-4 text-gray-500">
        <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
        <p className="text-xs font-medium leading-relaxed">
          {report.disclaimer}
        </p>
      </div>

    </div>
  );
}
