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
            <SiteHeader />
            <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
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
