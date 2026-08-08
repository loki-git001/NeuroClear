import { Activity } from "lucide-react";

export default function ProgressPage() {
  return (
    <div className="p-8">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-100">
          <Activity className="h-5 w-5 text-brand-700" />
        </div>
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-gray-900">
            Progress Tracker
          </h1>
          <p className="text-sm text-gray-500">
            Historical session trends and recovery insights
          </p>
        </div>
      </div>
    </div>
  );
}
