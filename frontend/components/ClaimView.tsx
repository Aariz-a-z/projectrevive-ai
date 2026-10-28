/**
 * Renders a Claim with its provenance.
 *
 * This component is where README section 4.2's central rule becomes visible:
 * a reader can always tell whether the report said something or the system
 * inferred it, and can open the supporting quote to check it. The evidence is
 * in a <details> so inspecting it costs one click and no navigation.
 */

import type { Claim } from "@/lib/types";

function SourceBadge({ source }: { source: Claim["source"] }) {
  const isStated = source === "stated";
  return (
    <span
      className={[
        "shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium tracking-wide uppercase",
        isStated
          ? "bg-stated-soft text-stated"
          : "bg-inferred-soft text-inferred",
      ].join(" ")}
    >
      {isStated ? "In report" : "Inferred"}
    </span>
  );
}

export function ClaimView({ claim }: { claim: Claim }) {
  const hasEvidence = claim.evidence.length > 0;

  return (
    <div className="rounded-md border border-border-subtle bg-surface p-3">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm leading-relaxed">{claim.value}</p>
        <SourceBadge source={claim.source} />
      </div>

      {hasEvidence && (
        <details className="group mt-2">
          <summary className="cursor-pointer list-none text-xs text-accent hover:underline">
            <span className="group-open:hidden">
              Show evidence ({claim.evidence.length})
            </span>
            <span className="hidden group-open:inline">Hide evidence</span>
          </summary>
          <ul className="mt-2 space-y-2">
            {claim.evidence.map((item, index) => (
              <li
                key={`${item.page}-${index}`}
                className="border-l-2 border-stated pl-3"
              >
                <p className="text-xs font-medium text-muted">
                  Page {item.page}
                </p>
                <blockquote className="mt-0.5 text-xs leading-relaxed text-foreground/85 italic">
                  &ldquo;{item.quote}&rdquo;
                </blockquote>
              </li>
            ))}
          </ul>
        </details>
      )}

      {claim.source === "inferred" && claim.reasoning && (
        <p className="mt-2 border-l-2 border-inferred pl-3 text-xs leading-relaxed text-muted">
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
          <span
            title={
              claim.evidence.length > 0
                ? `Page ${claim.evidence[0].page}: ${claim.evidence[0].quote}`
                : (claim.reasoning ?? "Inferred")
            }
            className={[
              "inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs",
              claim.source === "stated"
                ? "border-stated/30 bg-stated-soft text-stated"
                : "border-inferred/30 bg-inferred-soft text-inferred",
            ].join(" ")}
          >
            {claim.value}
            {claim.evidence.length > 0 && (
              <span className="opacity-60">p{claim.evidence[0].page}</span>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}
