import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import { SiteHeader } from "@/components/SiteHeader";
import { AuthProvider } from "@/lib/auth";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "ProjectRevive AI — Understand and improve any project report",
  description:
    "Upload an AI/ML project report and get a structured analysis: what the " +
    "project does, where it is weak, and what to improve — with every finding " +
    "traced to the page it came from.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="relative min-h-full">
        <div
          className="grid-surface pointer-events-none fixed inset-0 -z-10"
          aria-hidden="true"
        />
        <AuthProvider>
          <div className="flex min-h-screen flex-col">
            {/*
              First focusable element on every page. Without it, reaching the
              content means tabbing through the whole header each time, which
              is the single most tiring thing about navigating a site by
              keyboard. Visually hidden until focused.
            */}
            <a
              href="#main"
              className="sr-only focus:not-sr-only focus:absolute focus:top-3 focus:left-3 focus:z-50 focus:rounded-lg focus:bg-cyan focus:px-4 focus:py-2 focus:text-sm focus:font-semibold focus:text-[#04121c]"
            >
              Skip to main content
            </a>
            <SiteHeader />
            <main
              id="main"
              // Focusable target so the skip link actually moves focus, not
              // just the viewport.
              tabIndex={-1}
              className="mx-auto w-full max-w-6xl flex-1 px-4 py-8"
            >
              {children}
            </main>
            <footer className="border-t border-edge">
              <div className="mx-auto max-w-6xl px-4 py-5 text-xs leading-relaxed text-muted">
                ProjectRevive AI reports what it can trace to your document.
                Findings are labelled as stated in the report or inferred, and
                any citation it cannot verify against the page it names is
                rejected rather than shown.
              </div>
            </footer>
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
