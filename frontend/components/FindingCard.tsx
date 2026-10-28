/**
 * A single weakness or gap.
 *
 * Two things are always visible rather than tucked away, because they are what
 * let a reader judge the finding rather than just accept it:
 *
 * - whether it came from a deterministic rule or from the model, since only
 *   one of those can be read and checked;
 * - what backs it up — a quote for a weakness, or the terms that were searched
 *   for and not found in the case of a gap.
 */

import { Badge, type Accent } from "@/components/ui";
import type { Finding, Severity } from "@/lib/types";

const SEVERITY_ACCENT: Record<Severity, Accent> = {
  high: "rose",
  medium: "amber",
  low: "cyan",
};

const SEVERITY_LABEL: Record<Severity, string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
};

const SEVERITY_BAR: Record<Severity, string> = {
  high: "bg-rose",
  medium: "bg-amber",
  low: "bg-cyan",
};

export function FindingCard({ finding }: { finding: Finding }) {
  const isGap = finding.kind === "gap";

  return (
    <article className="panel-inset relative overflow-hidden rounded-lg p-4 pl-5">
      <span
        aria-hidden="true"
        className={`absolute inset-y-0 left-0 w-1 ${SEVERITY_BAR[finding.severity]}`}
      />

      <div className="flex flex-wrap items-start justify-between gap-2">
        <h4 className="text-sm leading-snug font-semibold">{finding.title}</h4>
        <div className="flex shrink-0 flex-wrap gap-1.5">
          <Badge accent={SEVERITY_ACCENT[finding.severity]}>
            {SEVERITY_LABEL[finding.severity]}
          </Badge>
          <Badge accent={isGap ? "violet" : "rose"}>
            {isGap ? "Missing" : "Present"}
          </Badge>
          <Badge
            accent={finding.detected_by === "rule" ? "green" : "amber"}
            title={
              finding.detected_by === "rule"
                ? `Found by the deterministic rule "${finding.rule_id}". You can read exactly what it checks.`
                : "Suggested by the language model. Worth verifying against the report yourself."
            }
          >
            {finding.detected_by === "rule" ? "Rule" : "Model"}
          </Badge>
        </div>
      </div>

      <p className="mt-2 text-xs leading-relaxed text-fg-dim">
        {finding.explanation}
      </p>

      {finding.evidence.length > 0 && (
        <ul className="mt-3 space-y-2">
          {finding.evidence.map((item, index) => (
            <li
              key={`${item.page}-${index}`}
              className="border-l-2 border-green pl-3"
            >
              <p className="font-mono text-[11px] text-green">
                page {item.page}
              </p>
              <blockquote className="mt-0.5 text-xs leading-relaxed text-muted italic">
                &ldquo;{item.quote}&rdquo;
              </blockquote>
            </li>
          ))}
        </ul>
      )}

      {isGap && finding.searched_for && (
        <p className="mt-3 border-l-2 border-violet pl-3 text-[11px] leading-relaxed text-muted">
          {finding.searched_for}
        </p>
      )}

      <p className="mt-3 font-mono text-[10px] tracking-wide text-muted uppercase">
        {finding.category.replace(/_/g, " ")}
        {finding.rule_id && ` · ${finding.rule_id}`}
      </p>
    </article>
  );
}
