"use client";

/**
 * Renders a Mermaid diagram, and fails usefully when it cannot.
 *
 * README section 4.6 asks for useful error handling when rendering fails. The
 * backend already refuses to emit a diagram it cannot parse back, so a
 * failure here means Mermaid rejected something the backend's structural
 * check did not anticipate. That is exactly the case where a blank panel is
 * the worst outcome: the user has no idea whether their project has no
 * architecture or the page is broken.
 *
 * So a failure shows the error and the diagram source, which is still useful
 * on its own -- it can be pasted into any Mermaid editor or a README.
 *
 * Mermaid is imported dynamically because it is large and browser-only;
 * importing it at module scope would pull it into the server bundle.
 */

import { useEffect, useId, useRef, useState } from "react";

import { Notice } from "@/components/ui";

/**
 * The result carries the chart it was produced from, so "is this stale?" is
 * derived rather than signalled by resetting state at the top of the effect.
 * That extra synchronous setState would force a second render on every change.
 */
type Result =
  | { chart: string; svg: string; error?: never }
  | { chart: string; error: string; svg?: never };

export function MermaidDiagram({
  chart,
  ariaLabel,
}: {
  chart: string;
  ariaLabel: string;
}) {
  const [result, setResult] = useState<Result | null>(null);
  const reactId = useId();
  // Mermaid needs a DOM-safe id; React's contains colons.
  const diagramId = useRef(`mermaid-${reactId.replace(/[^a-zA-Z0-9]/g, "")}`);

  const current = result?.chart === chart ? result : null;

  useEffect(() => {
    let active = true;

    (async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({
          startOnLoad: false,
          theme: "dark",
          darkMode: true,
          securityLevel: "strict",
          flowchart: { curve: "basis", padding: 14 },
          themeVariables: {
            background: "#0e1629",
            primaryColor: "#141f38",
            primaryTextColor: "#e9eefc",
            primaryBorderColor: "#2a3f6d",
            lineColor: "#4b8cf7",
            fontFamily: "var(--font-geist-sans), system-ui, sans-serif",
            fontSize: "13px",
          },
        });

        const { svg } = await mermaid.render(diagramId.current, chart);
        if (active) setResult({ chart, svg });
      } catch (error: unknown) {
        if (!active) return;
        setResult({
          chart,
          error:
            error instanceof Error
              ? error.message
              : "Mermaid could not render this.",
        });
      }
    })();

    return () => {
      active = false;
    };
  }, [chart]);

  if (current === null) {
    return (
      <div
        className="h-56 animate-pulse rounded-lg bg-panel-inset"
        aria-busy="true"
        aria-label={`Rendering ${ariaLabel}`}
      />
    );
  }

  if (current.error !== undefined) {
    return (
      <div className="space-y-3">
        <Notice tone="error" title="This diagram could not be drawn">
          <p>{current.error}</p>
          <p className="mt-1.5">
            The diagram source is below and is still valid Mermaid — paste it
            into any Mermaid editor or a README.
          </p>
        </Notice>
        <pre className="panel-inset overflow-x-auto rounded-lg p-3 font-mono text-[11px] leading-relaxed text-muted">
          {chart}
        </pre>
      </div>
    );
  }

  return (
    <figure className="space-y-2">
      <div
        role="img"
        aria-label={ariaLabel}
        className="overflow-x-auto rounded-lg bg-panel-inset p-4 [&_svg]:mx-auto [&_svg]:h-auto [&_svg]:max-w-full"
        // The SVG comes from Mermaid rendering backend-generated text whose
        // labels are escaped server-side, and securityLevel "strict" strips
        // scripts and inline handlers.
        dangerouslySetInnerHTML={{ __html: current.svg }}
      />
      <details>
        <summary className="cursor-pointer text-xs text-cyan hover:underline">
          Show diagram source
        </summary>
        <pre className="panel-inset mt-2 overflow-x-auto rounded-lg p-3 font-mono text-[11px] leading-relaxed text-muted">
          {chart}
        </pre>
      </details>
    </figure>
  );
}
