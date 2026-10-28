/**
 * Shared presentation primitives for the dark theme.
 *
 * Accent is a named semantic, not a free colour, so "evidence" is green
 * everywhere and "inference" is amber everywhere without each page choosing.
 */

import type { ReactNode } from "react";

export type Accent = "cyan" | "blue" | "violet" | "green" | "amber" | "rose";

export const ACCENT_TEXT: Record<Accent, string> = {
  cyan: "text-cyan",
  blue: "text-blue",
  violet: "text-violet",
  green: "text-green",
  amber: "text-amber",
  rose: "text-rose",
};

const ACCENT_CHIP: Record<Accent, string> = {
  cyan: "bg-cyan-soft text-cyan ring-cyan/25",
  blue: "bg-cyan-soft text-blue ring-blue/25",
  violet: "bg-violet-soft text-violet ring-violet/25",
  green: "bg-green-soft text-green ring-green/25",
  amber: "bg-amber-soft text-amber ring-amber/25",
  rose: "bg-rose-soft text-rose ring-rose/25",
};

export function Panel({
  children,
  className = "",
  as: Tag = "div",
}: {
  children: ReactNode;
  className?: string;
  as?: "div" | "section" | "article" | "aside";
}) {
  return <Tag className={`panel rounded-xl ${className}`}>{children}</Tag>;
}

export function PanelHeader({
  title,
  icon,
  accent = "cyan",
  right,
}: {
  title: string;
  icon?: ReactNode;
  accent?: Accent;
  right?: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-edge px-4 py-3">
      <div className="flex min-w-0 items-center gap-2.5">
        {icon && (
          <span className={`h-4 w-4 shrink-0 ${ACCENT_TEXT[accent]}`}>{icon}</span>
        )}
        <h2 className="truncate text-sm font-semibold tracking-tight">{title}</h2>
      </div>
      {right}
    </div>
  );
}

export function Badge({
  children,
  accent = "cyan",
  title,
}: {
  children: ReactNode;
  accent?: Accent;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset ${ACCENT_CHIP[accent]}`}
    >
      {children}
    </span>
  );
}

export function StatTile({
  value,
  label,
  accent = "cyan",
}: {
  value: ReactNode;
  label: string;
  accent?: Accent;
}) {
  return (
    <div className="panel-inset rounded-lg px-3 py-2.5 text-center">
      <p className={`text-lg leading-tight font-semibold ${ACCENT_TEXT[accent]}`}>
        {value}
      </p>
      <p className="mt-0.5 text-[11px] text-muted">{label}</p>
    </div>
  );
}

export function Button({
  children,
  onClick,
  type = "button",
  variant = "primary",
  disabled,
  className = "",
}: {
  children: ReactNode;
  onClick?: () => void;
  type?: "button" | "submit";
  variant?: "primary" | "ghost" | "danger";
  disabled?: boolean;
  className?: string;
}) {
  const styles = {
    primary:
      "bg-gradient-to-r from-cyan to-blue text-[#04121c] hover:brightness-110 font-semibold",
    ghost:
      "border border-edge-bright bg-panel-inset text-fg-dim hover:text-fg hover:border-cyan/40",
    danger: "border border-rose/40 bg-rose-soft text-rose hover:brightness-125",
  }[variant];

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${styles} ${className}`}
    >
      {children}
    </button>
  );
}

export function Notice({
  tone = "info",
  title,
  children,
}: {
  tone?: "info" | "caution" | "error";
  title?: string;
  children: ReactNode;
}) {
  const styles = {
    info: "border-edge-bright bg-panel-inset text-fg-dim",
    caution: "border-amber/35 bg-amber-soft/60 text-amber",
    error: "border-rose/40 bg-rose-soft/60 text-rose",
  }[tone];

  return (
    <div
      role={tone === "error" ? "alert" : undefined}
      className={`rounded-lg border px-4 py-3 text-sm leading-relaxed ${styles}`}
    >
      {title && <p className="mb-1 font-semibold">{title}</p>}
      <div className="[&_code]:font-mono [&_code]:text-[12px]">{children}</div>
    </div>
  );
}

export function Field({
  label,
  hint,
  error,
  children,
}: {
  label: string;
  hint?: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-medium tracking-wide text-fg-dim">
        {label}
      </span>
      {children}
      {error ? (
        <span className="mt-1.5 block text-xs text-rose">{error}</span>
      ) : hint ? (
        <span className="mt-1.5 block text-xs text-muted">{hint}</span>
      ) : null}
    </label>
  );
}

export const inputClass =
  "w-full rounded-lg border border-edge bg-panel-inset px-3 py-2 text-sm text-fg " +
  "placeholder:text-muted focus:border-cyan/50 focus:outline-none";

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
        <h3 className="text-sm font-semibold tracking-tight">{title}</h3>
        {description && <p className="mt-0.5 text-xs text-muted">{description}</p>}
      </div>
      {children}
    </section>
  );
}
