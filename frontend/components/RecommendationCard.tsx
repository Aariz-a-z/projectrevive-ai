"use client";

/**
 * One ranked recommendation.
 *
 * The score is shown with its own breakdown, open to inspection. README
 * section 4.4 forbids presenting an arbitrary score as a validated
 * measurement, so the components and the weights that produced the number are
 * one click away rather than hidden behind a bar.
 *
 * Trade-offs sit next to benefits at the same visual weight. A card that
 * displayed only the upside would be advertising, not analysis.
 */

import { useState } from "react";

import { Badge, type Accent } from "@/components/ui";
import type { Recommendation } from "@/lib/types";

const MATCH_LABEL: Record<Recommendation["matched_by"], string> = {
  knowledge: "Addresses a finding",
  content: "Similar project",
  both: "Addresses a finding",
};

const MATCH_ACCENT: Record<Recommendation["matched_by"], Accent> = {
  knowledge: "green",
  content: "violet",
  both: "green",
};

const COMPLEXITY_ACCENT: Record<Recommendation["complexity"], Accent> = {
  low: "green",
  medium: "amber",
  high: "rose",
};

function Bar({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-24 shrink-0 text-[11px] text-muted">{label}</span>
      <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-[#0a1222]">
        <span
          className="block h-full bg-cyan"
          style={{ width: `${Math.round(value * 100)}%` }}
        />
      </span>
      <span className="w-9 shrink-0 text-right font-mono text-[11px] text-fg-dim">
        {value.toFixed(2)}
      </span>
    </div>
  );
}

export function RecommendationCard({
  recommendation: r,
  rank,
}: {
  recommendation: Recommendation;
  rank: number;
}) {
  const [open, setOpen] = useState(false);

  return (
    <article className="panel-inset rounded-lg p-4">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-md bg-panel font-mono text-xs text-cyan ring-1 ring-edge">
          {rank}
        </span>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <h4 className="text-sm leading-snug font-semibold">{r.title}</h4>
            <div className="flex shrink-0 flex-wrap gap-1.5">
              <Badge accent={MATCH_ACCENT[r.matched_by]}>
                {MATCH_LABEL[r.matched_by]}
              </Badge>
              <Badge accent={COMPLEXITY_ACCENT[r.complexity]}>
                {r.complexity} effort
              </Badge>
              {r.cost !== "none" && <Badge accent="amber">{r.cost} cost</Badge>}
            </div>
          </div>

          <p className="mt-2 text-xs leading-relaxed text-fg-dim">{r.reason}</p>

          {r.addresses_findings.length > 0 && (
            <p className="mt-2 text-[11px] text-muted">
              Addresses:{" "}
              <span className="text-green">
                {r.addresses_findings.join("; ")}
              </span>
            </p>
          )}

          {r.evidence.length > 0 && (
            <blockquote className="mt-2 border-l-2 border-green pl-3 text-xs leading-relaxed text-muted italic">
              &ldquo;{r.evidence[0].quote}&rdquo;
              <span className="ml-1 font-mono text-[10px] not-italic text-green">
                p{r.evidence[0].page}
              </span>
            </blockquote>
          )}

          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="mt-3 text-xs text-cyan hover:underline"
          >
            {open ? "Hide detail" : "Show detail, trade-offs and score"}
          </button>

          {open && (
            <div className="mt-3 space-y-4 border-t border-edge pt-3">
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <p className="mb-1 text-[11px] font-medium tracking-wide text-muted uppercase">
                    Currently
                  </p>
                  <p className="text-xs leading-relaxed text-fg-dim">
                    {r.current_approach}
                  </p>
                </div>
                <div>
                  <p className="mb-1 text-[11px] font-medium tracking-wide text-muted uppercase">
                    Proposed
                  </p>
                  <p className="text-xs leading-relaxed text-fg-dim">
                    {r.proposed_approach}
                  </p>
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <p className="mb-1 text-[11px] font-medium tracking-wide text-green uppercase">
                    Expected benefits
                  </p>
                  <ul className="list-disc space-y-1 pl-4 text-xs leading-relaxed text-muted">
                    {r.expected_benefits.map((b, i) => (
                      <li key={i}>{b}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <p className="mb-1 text-[11px] font-medium tracking-wide text-amber uppercase">
                    Trade-offs
                  </p>
                  <ul className="list-disc space-y-1 pl-4 text-xs leading-relaxed text-muted">
                    {r.trade_offs.map((t, i) => (
                      <li key={i}>{t}</li>
                    ))}
                  </ul>
                </div>
              </div>

              <div>
                <p className="mb-1 text-[11px] font-medium tracking-wide text-muted uppercase">
                  How to do it
                </p>
                <ol className="list-decimal space-y-1 pl-4 text-xs leading-relaxed text-muted">
                  {r.implementation_steps.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ol>
              </div>

              <div>
                <p className="mb-1 text-[11px] font-medium tracking-wide text-muted uppercase">
                  How to check it worked
                </p>
                <p className="text-xs leading-relaxed text-muted">
                  {r.validation_method}
                </p>
              </div>

              {r.dependencies.length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="text-[11px] text-muted">Needs:</span>
                  {r.dependencies.map((d) => (
                    <Badge key={d} accent="cyan">
                      {d}
                    </Badge>
                  ))}
                </div>
              )}

              <div className="panel rounded-lg p-3">
                <p className="mb-2 text-[11px] font-medium tracking-wide text-muted uppercase">
                  How this was scored
                </p>
                <div className="space-y-1.5">
                  <Bar label="Relevance" value={r.score.relevance} />
                  <Bar label="Feasibility" value={r.score.feasibility} />
                  <Bar label="Impact (est.)" value={r.score.expected_impact} />
                  <Bar label="Effort cost" value={r.score.effort_penalty} />
                  <Bar label="Money cost" value={r.score.cost_penalty} />
                </div>
                <p className="mt-2 font-mono text-[10px] leading-relaxed text-muted">
                  {Object.entries(r.score.weights)
                    .map(([k, v]) => `${v}×${k}`)
                    .join("  ")}
                </p>
                <p className="mt-1.5 text-[11px] leading-relaxed text-muted">
                  A weighted sum with the weights above, not a measured
                  quantity. Impact is a hand-written estimate that is the same
                  for every project matching this entry.
                </p>
              </div>

              {r.constraint_notes.length > 0 && (
                <ul className="space-y-1 border-l-2 border-amber pl-3 text-[11px] leading-relaxed text-amber">
                  {r.constraint_notes.map((n, i) => (
                    <li key={i}>{n}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>

        <div className="shrink-0 text-right">
          <p className="font-mono text-base leading-none font-semibold text-cyan">
            {r.score.final.toFixed(2)}
          </p>
          <p className="mt-0.5 text-[10px] text-muted">score</p>
        </div>
      </div>
    </article>
  );
}
