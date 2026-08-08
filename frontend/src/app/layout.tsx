import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "./sidebar";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "NeuroClear — Clinical Dysarthria Screening",
  description:
    "AI-powered speech pathology analysis platform for objective dysarthria detection and clinical reporting.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${inter.variable} h-full`}>
      <body className="h-full">
        <div className="flex h-screen overflow-hidden">
          {/* ── Persistent Sidebar (never re-renders on route change) ── */}
          <Sidebar />

          {/* ── Main content area — route pages mount/unmount here ──── */}
          <main className="flex-1 overflow-y-auto">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
