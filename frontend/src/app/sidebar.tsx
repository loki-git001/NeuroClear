"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Brain, Mic, Stethoscope, LineChart } from "lucide-react";
import type { LucideIcon } from "lucide-react";

/* ── Navigation items ────────────────────────────────────────────────────── */

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

const NAV_ITEMS: NavItem[] = [
  { href: "/screening", label: "Diagnostic Screening", icon: Stethoscope },
  { href: "/practice", label: "Daily Practice", icon: Mic },
  { href: "/progress", label: "Progress Tracker", icon: LineChart },
];

/* ── Sidebar component ───────────────────────────────────────────────────── */

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex w-64 flex-col border-r border-sidebar-border bg-sidebar-bg">
      {/* ── Brand header ─────────────────────────────────────────────── */}
      <Link href="/" className="flex items-center gap-3 border-b border-sidebar-border px-6 py-5 transition-colors hover:bg-brand-950/50">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 shadow-md shadow-brand-600/30">
          <Brain className="h-5 w-5 text-white" />
        </div>
        <div>
          <h1 className="text-lg font-bold tracking-tight text-white">
            NeuroClear
          </h1>
          <p className="text-[11px] font-medium tracking-widest text-sidebar-text uppercase">
            Speech Analysis
          </p>
        </div>
      </Link>

      {/* ── Navigation links ─────────────────────────────────────────── */}
      <nav className="flex-1 space-y-1 px-3 py-4">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const isActive = pathname === href;

          return (
            <Link
              key={href}
              href={href}
              className={`
                group flex items-center gap-3 rounded-lg px-3 py-2.5
                text-sm font-medium transition-all duration-150
                ${
                  isActive
                    ? "bg-sidebar-active-bg text-white shadow-sm"
                    : "text-sidebar-text hover:bg-sidebar-active-bg/60 hover:text-sidebar-text-hover"
                }
              `}
            >
              <Icon
                className={`h-[18px] w-[18px] shrink-0 transition-colors duration-150 ${
                  isActive
                    ? "text-brand-400"
                    : "text-sidebar-text group-hover:text-brand-400"
                }`}
              />
              {label}

              {/* Active indicator pill */}
              {isActive && (
                <span className="ml-auto h-1.5 w-1.5 rounded-full bg-brand-400" />
              )}
            </Link>
          );
        })}
      </nav>

      {/* ── Footer ───────────────────────────────────────────────────── */}
      <div className="border-t border-sidebar-border px-6 py-4">
        <p className="text-[11px] text-sidebar-text">
          NeuroClear v1.0.0
        </p>
        <p className="text-[10px] text-sidebar-text/50">
          Clinical Research Use Only
        </p>
      </div>
    </aside>
  );
}