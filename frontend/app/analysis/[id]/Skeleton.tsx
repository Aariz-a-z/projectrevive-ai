/**
 * Loading placeholder, shared between the Suspense fallback for the
 * prerendered shell and the in-component fetch state, so the two match.
 */
export function AnalysisSkeleton() {
  return (
    <div className="space-y-4" aria-busy="true">
      <div className="h-8 w-2/3 animate-pulse rounded-lg bg-panel-inset" />
      <div className="h-24 animate-pulse rounded-xl bg-panel-inset" />
      <div className="h-10 w-96 max-w-full animate-pulse rounded-lg bg-panel-inset" />
      <div className="h-72 animate-pulse rounded-xl bg-panel-inset" />
      <p className="text-xs text-muted">Loading analysis…</p>
    </div>
  );
}
