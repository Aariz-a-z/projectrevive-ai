import { Suspense } from "react";

import { AnalysisView } from "./AnalysisView";
import { AnalysisSkeleton } from "./Skeleton";

/**
 * Server shell for the analysis route.
 *
 * The analysis id is only known at request time, and `cacheComponents` is on,
 * so the client view that reads it must sit inside a Suspense boundary. That
 * lets the surrounding layout prerender as a static shell while the analysis
 * streams in.
 */
export default function AnalysisPage() {
  return (
    <Suspense fallback={<AnalysisSkeleton />}>
      <AnalysisView />
    </Suspense>
  );
}
