"use client";

import { useEffect, useState } from "react";
import { Activity, Calendar, TrendingUp, Waves, ArrowRight } from "lucide-react";
import Link from "next/link";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";

// ── Historical Mock Data ──────────────────────────────────────────────────
const historicalData = [
  { date: "Jul 15", wpm: 55, tremors: 8, severity: "Severe" },
  { date: "Jul 22", wpm: 62, tremors: 7, severity: "Moderate-Severe" },
  { date: "Jul 29", wpm: 68, tremors: 5, severity: "Moderate-Severe" },
  { date: "Aug 05", wpm: 60, tremors: 4, severity: "Moderate" },
];

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-3 shadow-lg">
        <p className="mb-1 text-xs font-bold text-gray-500">{label}</p>
        <p className="text-sm font-semibold text-brand-600">
          Speaking Rate: {payload[0].value} WPM
        </p>
      </div>
    );
  }
  return null;
};

export default function ProgressPage() {
  const [chartData, setChartData] = useState(historicalData);
  const [isLoaded, setIsLoaded] = useState(false);

  // ── Dynamic Live Data Injection ─────────────────────────────────────────
  useEffect(() => {
    try {
      const storedReport = localStorage.getItem("neuroclear_latest_report");
      if (storedReport) {
        const parsed = JSON.parse(storedReport);

        // Extract WPM from the Gemini text using Regex
        const wpmMatch = parsed.prosody_evaluation?.match(/(\d+(\.\d+)?)\s*WPM/i);
        const extractedWpm = wpmMatch ? Math.round(parseFloat(wpmMatch[1])) : 85;

        // Extract Tremors and Severity
        const tremorCount = parsed.detected_events ? parsed.detected_events.length : 0;
        const currentSeverity = parsed.dysarthria_severity || "Normal";

        // Append today's actual live session to the historical data
        const liveSession = {
          date: "Today",
          wpm: extractedWpm,
          tremors: tremorCount,
          severity: currentSeverity,
        };

        setChartData([...historicalData, liveSession]);
      }
    } catch (e) {
      console.error("Failed to parse live report for progress tracker", e);
    }
    setIsLoaded(true);
  }, []);

  if (!isLoaded) return null; // Prevent hydration mismatch

  // Dynamic calculations for top cards
  const latest = chartData[chartData.length - 1];
  const previous = chartData.length > 1 ? chartData[chartData.length - 2] : latest;

  const wpmDiff = latest.wpm - previous.wpm;
  const wpmPercent = previous.wpm > 0 ? Math.round((wpmDiff / previous.wpm) * 100) : 0;
  const tremorDiff = latest.tremors - previous.tremors;

  return (
    <div className="min-h-full bg-gray-50 p-8 pb-20">
      {/* ── Page Header ──────────────────────────────────────────────── */}
      <div className="mb-8 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-100">
            <TrendingUp className="h-5 w-5 text-brand-700" />
          </div>
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-gray-900">
              Progress Tracker
            </h1>
            <p className="text-sm text-gray-500">
              Longitudinal analysis of your speech rehabilitation journey
            </p>
          </div>
        </div>
        <Link
          href="/screening"
          className="hidden sm:inline-flex items-center gap-2 rounded-xl bg-white px-5 py-2.5 text-sm font-semibold text-gray-700 border border-gray-200 shadow-sm transition-all hover:bg-gray-50 active:scale-95"
        >
          <Activity className="h-4 w-4" /> New Assessment
        </Link>
      </div>

      {/* ── Dynamic Top Stat Cards ───────────────────────────────────── */}
      <div className="mb-8 grid grid-cols-1 gap-6 md:grid-cols-3">
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
          <p className="text-sm font-semibold text-gray-500">Latest Speaking Rate</p>
          <div className="mt-2 flex items-end gap-2">
            <h2 className="text-3xl font-bold text-gray-900">{latest.wpm}</h2>
            <span className="mb-1 text-sm font-medium text-gray-500">WPM</span>
          </div>
          <p className={`mt-2 text-xs font-medium flex items-center gap-1 ${wpmDiff >= 0 ? "text-emerald-600" : "text-red-600"}`}>
            <TrendingUp className={`h-3 w-3 ${wpmDiff < 0 ? "rotate-180" : ""}`} />
            {wpmPercent > 0 ? "+" : ""}{wpmPercent}% from last session
          </p>
        </div>

        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
          <p className="text-sm font-semibold text-gray-500">Latest Tremor Events</p>
          <div className="mt-2 flex items-end gap-2">
            <h2 className="text-3xl font-bold text-gray-900">{latest.tremors}</h2>
            <span className="mb-1 text-sm font-medium text-gray-500">event{latest.tremors !== 1 ? 's' : ''}</span>
          </div>
          <p className={`mt-2 text-xs font-medium flex items-center gap-1 ${tremorDiff <= 0 ? "text-emerald-600" : "text-red-600"}`}>
            <TrendingUp className={`h-3 w-3 ${tremorDiff > 0 ? "" : "rotate-180"}`} />
            {tremorDiff > 0 ? "+" : ""}{tremorDiff} from last session
          </p>
        </div>

        <div className="rounded-2xl border border-blue-100 bg-blue-50 p-6 shadow-sm">
          <p className="text-sm font-semibold text-blue-700">Clinical Status</p>
          <div className="mt-2">
            <h2 className="text-2xl font-bold text-blue-900">{latest.severity}</h2>
          </div>
          <p className="mt-2 text-xs font-medium text-blue-600">
            Updated: {latest.date}
          </p>
        </div>
      </div>

      {/* ── Charts Grid ──────────────────────────────────────────────── */}
      <div className="mb-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Speaking Rate Chart */}
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
          <div className="mb-6 flex items-center gap-2">
            <Waves className="h-5 w-5 text-brand-600" />
            <h3 className="text-lg font-bold text-gray-900">Speaking Rate Progression</h3>
          </div>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5E7EB" />
                <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#6B7280' }} dy={10} />
                <YAxis domain={[0, 150]} axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#6B7280' }} />
                <Tooltip content={<CustomTooltip />} cursor={{ stroke: '#E5E7EB', strokeWidth: 2 }} />
                <ReferenceLine y={130} stroke="#10B981" strokeDasharray="3 3" label={{ position: 'top', value: 'Healthy Min (130)', fill: '#10B981', fontSize: 10 }} />
                <Line type="monotone" dataKey="wpm" stroke="#2563EB" strokeWidth={3} dot={{ r: 4, fill: '#2563EB', strokeWidth: 2, stroke: '#FFFFFF' }} activeDot={{ r: 6 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Tremor Events Chart */}
        <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
          <div className="mb-6 flex items-center gap-2">
            <Activity className="h-5 w-5 text-brand-600" />
            <h3 className="text-lg font-bold text-gray-900">Motor Disfluency Events</h3>
          </div>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5E7EB" />
                <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#6B7280' }} dy={10} />
                <YAxis allowDecimals={false} axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#6B7280' }} />
                <Tooltip cursor={{ fill: '#F3F4F6' }} contentStyle={{ borderRadius: '8px', border: '1px solid #E5E7EB', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                <Bar dataKey="tremors" fill="#F59E0B" radius={[4, 4, 0, 0]} barSize={40} name="Tremor Events" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* ── Session History Table ──────────────────────────────────────── */}
      <div className="rounded-2xl border border-gray-200 bg-white shadow-sm overflow-hidden">
        <div className="border-b border-gray-200 px-6 py-5">
          <h3 className="text-lg font-bold text-gray-900">Session History</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50 border-b border-gray-200 text-xs font-bold uppercase tracking-wider text-gray-500">
              <tr>
                <th className="px-6 py-4">Date</th>
                <th className="px-6 py-4">Clinical Severity</th>
                <th className="px-6 py-4 text-right">Speaking Rate</th>
                <th className="px-6 py-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {chartData.slice().reverse().map((session, idx) => (
                <tr key={idx} className="transition-colors hover:bg-gray-50">
                  <td className="px-6 py-4 font-medium text-gray-900 flex items-center gap-2">
                    <Calendar className="h-4 w-4 text-gray-400" /> {session.date === "Today" ? "Today" : `${session.date}, 2026`}
                  </td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${session.severity.includes('Severe')
                      ? 'bg-red-50 text-red-700 border border-red-100'
                      : session.severity.includes('Moderate')
                        ? 'bg-amber-50 text-amber-700 border border-amber-100'
                        : 'bg-emerald-50 text-emerald-700 border border-emerald-100'
                      }`}>
                      {session.severity}
                    </span>
                  </td>
                  <td className="px-6 py-4 font-mono text-gray-600 text-right">
                    {session.wpm} WPM
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button className="text-brand-600 hover:text-brand-800 font-medium inline-flex items-center gap-1 transition-colors">
                      View <ArrowRight className="h-3 w-3" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
