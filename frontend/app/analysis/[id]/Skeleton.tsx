/**
 * Loading placeholder, shared between the Suspense fallback for the prerendered
 * shell and the in-component fetch state, so the two look identical.
 */
export function AnalysisSkeleton() {
  return (
    <div className="space-y-3" aria-busy="true">
      <div className="h-7 w-2/3 animate-pulse rounded bg-surface-muted" />
      <div className="h-20 animate-pulse rounded bg-surface-muted" />
      <div className="h-48 animate-pulse rounded bg-surface-muted" />
      <p className="text-xs text-muted">Loading analysis&hellip;</p>
    </div>
  );
}
