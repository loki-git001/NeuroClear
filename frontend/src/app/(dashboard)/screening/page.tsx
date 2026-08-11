import { Stethoscope } from "lucide-react";
import ScreeningInterface from "./screening-interface";
import { CLINICAL_PASSAGES } from "@/lib/constants";

export default function ScreeningPage() {
  return (
    <div className="min-h-full bg-gray-50 p-8">

      {/* ── Page header ───────────────────────────────────────────────── */}
      <div className="mb-8 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-100">
          <Stethoscope className="h-5 w-5 text-brand-700" />
        </div>
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-gray-900">
            Diagnostic Screening
          </h1>
          <p className="text-sm text-gray-500">
            Record a reading sample for full pipeline AI analysis
          </p>
        </div>
      </div>

      {/* ── Recording interface ────────────────────────────────────────── */}
      <div className="mx-auto w-full max-w-5xl">
        <ScreeningInterface passages={CLINICAL_PASSAGES} />
      </div>

    </div>
  );
}
