/**
 * Technologies grouped by verdict.
 *
 * A "keep" carries the page it was found on; an "add" carries the
 * recommendation that asked for it. Neither appears without its support,
 * because the backend schema refuses to construct one that way — so there is
 * no case here where the reason is missing.
 */

import { Badge, type Accent } from "@/components/ui";
import type { StackEntry, StackVerdict } from "@/lib/types";

const VERDICT_ACCENT: Record<StackVerdict, Accent> = {
  keep: "green",
  add: "cyan",
  replace: "amber",
};

export function StackList({
  entries,
  empty,
}: {
  entries: StackEntry[];
  empty: string;
}) {
  if (entries.length === 0) {
    return <p className="text-sm text-muted italic">{empty}</p>;
  }

  return (
    <ul className="space-y-2">
      {entries.map((entry) => (
        <li key={`${entry.verdict}-${entry.name}`} className="panel-inset rounded-lg p-3">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="flex items-baseline gap-2">
              <span className="font-mono text-sm font-semibold">
                {entry.name}
              </span>
              <span className="text-[11px] text-muted">{entry.category}</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {entry.replaces && (
                <Badge accent="amber">replaces {entry.replaces}</Badge>
              )}
              {entry.migration_complexity && (
                <Badge accent={VERDICT_ACCENT[entry.verdict]}>
                  {entry.migration_complexity} effort
                </Badge>
              )}
              {entry.evidence.length > 0 && (
                <Badge accent="green">p{entry.evidence[0].page}</Badge>
              )}
            </div>
          </div>

          <p className="mt-1.5 text-xs leading-relaxed text-muted">
            {entry.rationale}
          </p>

          {entry.evidence.length > 0 && (
            <blockquote className="mt-2 border-l-2 border-green pl-3 text-xs leading-relaxed text-muted italic">
              &ldquo;{entry.evidence[0].quote}&rdquo;
            </blockquote>
          )}

          {entry.introduced_by.length > 0 && (
            <p className="mt-2 font-mono text-[10px] tracking-wide text-muted uppercase">
              from {entry.introduced_by.join(", ")}
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}
