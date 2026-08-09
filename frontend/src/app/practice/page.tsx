import { Mic } from "lucide-react";

export default function PracticePage() {
  return (
    <div className="p-8">
      <div className="flex items-center gap-3">
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
    </div>
  );
}