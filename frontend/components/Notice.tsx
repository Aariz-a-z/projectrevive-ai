/**
 * Status and caveat panels.
 *
 * `caution` is used for anything the user must not mistake for a verified
 * result: mock-provider output, unverifiable citations, injection warnings.
 */

import type { ReactNode } from "react";

type Tone = "info" | "caution" | "error";

const TONES: Record<Tone, string> = {
  info: "border-border-strong bg-surface-muted text-foreground",
  caution: "border-inferred/40 bg-inferred-soft text-inferred",
  error: "border-danger/40 bg-danger-soft text-danger",
};

export function Notice({
  tone = "info",
  title,
  children,
}: {
  tone?: Tone;
  title?: string;
  children: ReactNode;
}) {
  return (
    <div
      role={tone === "error" ? "alert" : undefined}
      className={`rounded-md border px-4 py-3 text-sm leading-relaxed ${TONES[tone]}`}
    >
      {title && <p className="mb-1 font-semibold">{title}</p>}
      {children}
    </div>
  );
}

export function Section({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-base font-semibold tracking-tight">{title}</h2>
        {description && (
          <p className="mt-0.5 text-xs text-muted">{description}</p>
        )}
      </div>
      {children}
    </section>
  );
}
