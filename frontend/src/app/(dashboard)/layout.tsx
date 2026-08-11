import { Sidebar } from "./sidebar";

export default function DashboardLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <div className="flex h-screen overflow-hidden">
      {/* ── Persistent Sidebar (never re-renders on route change) ── */}
      <Sidebar />

      {/* ── Main content area — route pages mount/unmount here ──── */}
      <main className="flex-1 overflow-y-auto">
        {children}
      </main>
    </div>
  );
}
