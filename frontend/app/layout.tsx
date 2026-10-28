import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "ProjectRevive AI",
  description:
    "Analyses an existing AI/ML project report and recommends evidence-based, " +
    "explainable improvements.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <header className="border-b border-border-subtle bg-surface">
          <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
            <Link href="/" className="flex items-baseline gap-2">
              <span className="text-sm font-semibold tracking-tight">
                ProjectRevive
              </span>
              <span className="text-[11px] font-medium tracking-widest text-muted uppercase">
                AI
              </span>
            </Link>
            <nav className="flex items-center gap-4 text-sm">
              <Link href="/upload" className="text-muted hover:text-foreground">
                Analyse a report
              </Link>
            </nav>
          </div>
        </header>

        <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">
          {children}
        </main>

        <footer className="border-t border-border-subtle bg-surface">
          <div className="mx-auto max-w-5xl px-4 py-4 text-xs leading-relaxed text-muted">
            ProjectRevive AI is a project-analysis tool. Its recommendations are
            suggestions to evaluate, not validated findings, and any figures it
            shows are labelled with where they came from.
          </div>
        </footer>
      </body>
    </html>
  );
}
