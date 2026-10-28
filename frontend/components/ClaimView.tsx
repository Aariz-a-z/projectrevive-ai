/**
 * Renders a Claim with its provenance.
 *
 * This is where the product's central rule becomes visible: a reader can
 * always tell whether the report said something or the system inferred it, and
 * can open the supporting quote to check it. Green means found in the report,
 * amber means inferred — the same meaning those colours carry everywhere else.
 */

import { Badge } from "@/components/ui";
import type { Claim } from "@/lib/types";

export function ClaimView({ claim }: { claim: Claim }) {
  const stated = claim.source === "stated";

  return (
    <div className="panel-inset rounded-lg p-3">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm leading-relaxed text-fg-dim">{claim.value}</p>
        <Badge accent={stated ? "green" : "amber"}>
          {stated ? "In report" : "Inferred"}
        </Badge>
      </div>

      {claim.evidence.length > 0 && (
        <details className="group mt-2">
          <summary className="cursor-pointer list-none text-xs text-cyan hover:underline">
            <span className="group-open:hidden">
              Show evidence ({claim.evidence.length})
            </span>
            <span className="hidden group-open:inline">Hide evidence</span>
          </summary>
          <ul className="mt-2 space-y-2">
            {claim.evidence.map((item, index) => (
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
        </details>
      )}

      {!stated && claim.reasoning && (
        <p className="mt-2 border-l-2 border-amber pl-3 text-xs leading-relaxed text-muted">
          {claim.reasoning}
        </p>
      )}
    </div>
  );
}

export function ClaimList({
  claims,
  emptyMessage,
}: {
  claims: Claim[];
  emptyMessage: string;
}) {
  if (claims.length === 0) {
    return <p className="text-sm text-muted italic">{emptyMessage}</p>;
  }
  return (
    <div className="space-y-2">
      {claims.map((claim, index) => (
        <ClaimView key={`${claim.value}-${index}`} claim={claim} />
      ))}
    </div>
  );
}

/** Compact inline form, for stack items where the value is a single token. */
export function ClaimChips({ claims }: { claims: Claim[] }) {
  if (claims.length === 0) {
    return <span className="text-sm text-muted italic">None identified</span>;
  }
  return (
    <ul className="flex flex-wrap gap-1.5">
      {claims.map((claim, index) => (
        <li key={`${claim.value}-${index}`}>
          <Badge
            accent={claim.source === "stated" ? "green" : "amber"}
            title={
              claim.evidence.length > 0
                ? `Page ${claim.evidence[0].page}: ${claim.evidence[0].quote}`
                : (claim.reasoning ?? "Inferred")
            }
          >
            {claim.value}
            {claim.evidence.length > 0 && (
              <span className="font-mono opacity-60">
                p{claim.evidence[0].page}
              </span>
            )}
          </Badge>
        </li>
      ))}
    </ul>
  );
}
