"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { ClaimChips, ClaimList, ClaimView } from "@/components/ClaimView";
import { Notice, Section } from "@/components/Notice";
import { ApiError, getAnalysis } from "@/lib/api";
import type { AnalysisDetail } from "@/lib/types";

import { AnalysisSkeleton } from "./Skeleton";

function ProvenanceBar({ analysis }: { analysis: AnalysisDetail }) {
  const { stated, inferred, total } = analysis.claim_counts;
  const statedPct = total > 0 ? Math.round((stated / total) * 100) : 0;

  return (
    <div className="rounded-md border border-border-subtle bg-surface p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold tracking-tight">
          Where this analysis comes from
        </h2>
        <p className="font-mono text-xs text-muted">
          {analysis.provenance.provider} / {analysis.provenance.model}
        </p>
      </div>

      <div
        className="mt-3 flex h-2 overflow-hidden rounded-full bg-surface-muted"
        role="img"
        aria-label={`${stated} of ${total} findings are stated in the report; ${inferred} are inferred.`}
      >
        <div className="bg-stated" style={{ width: `${statedPct}%` }} />
        <div className="bg-inferred" style={{ width: `${100 - statedPct}%` }} />
      </div>

      <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted">
        <span>
          <span className="mr-1 inline-block h-2 w-2 rounded-full bg-stated align-middle" />
          {stated} stated in the report
        </span>
        <span>
          <span className="mr-1 inline-block h-2 w-2 rounded-full bg-inferred align-middle" />
          {inferred} inferred
        </span>
        {analysis.provenance.usage.input_tokens > 0 && (
          <span className="font-mono">
            {analysis.provenance.usage.input_tokens.toLocaleString()} in /{" "}
            {analysis.provenance.usage.output_tokens.toLocaleString()} out
          </span>
        )}
      </div>
    </div>
  );
}

export function AnalysisView() {
  const { id } = useParams<{ id: string }>();
  const [analysis, setAnalysis] = useState<AnalysisDetail | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  useEffect(() => {
    if (!id) return;
    let active = true;
    getAnalysis(id)
      .then((data) => active && setAnalysis(data))
      .catch((err: unknown) => {
        if (!active) return;
        setError(
          err instanceof ApiError
            ? err
            : new ApiError(0, "unknown", "Could not load that analysis."),
        );
      });
    return () => {
      active = false;
    };
  }, [id]);

  if (error) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <Notice tone="error" title="This analysis could not be loaded">
          {error.message}
        </Notice>
        <Link href="/upload" className="text-sm text-accent hover:underline">
          Analyse another report
        </Link>
      </div>
    );
  }

  if (!analysis) {
    return <AnalysisSkeleton />;
  }

  const { profile } = analysis;

  return (
    <div className="space-y-8">
      <header className="space-y-2">
        <p className="font-mono text-xs text-muted">
          {analysis.filename} &middot; {analysis.page_count} pages &middot;{" "}
          {new Date(analysis.created_at).toLocaleString()}
        </p>
        <h1 className="text-2xl leading-tight font-semibold tracking-tight">
          {profile.title.value}
        </h1>
        <p className="text-sm text-muted">
          Domain: {profile.domain.value}
          {profile.domain.source === "inferred" && " (inferred)"}
        </p>
      </header>

      {analysis.provenance.is_mock && (
        <Notice tone="caution" title="This is mock-provider output">
          No language model produced this. The findings below come from keyword
          matching over your document, so treat them as a structural
          demonstration rather than an analysis of your project&rsquo;s merits.
        </Notice>
      )}

      <ProvenanceBar analysis={analysis} />

      {analysis.warnings.length > 0 && (
        <Notice tone="caution" title="Caveats on this analysis">
          <ul className="list-disc space-y-1 pl-4">
            {analysis.warnings.map((warning, index) => (
              <li key={index}>{warning}</li>
            ))}
          </ul>
        </Notice>
      )}

      <Section
        title="Problem statement"
        description="What the report says this project set out to solve."
      >
        <ClaimView claim={profile.problem_statement} />
      </Section>

      {profile.objectives.length > 0 && (
        <Section title="Objectives">
          <ClaimList claims={profile.objectives} emptyMessage="None found." />
        </Section>
      )}

      <Section
        title="Methodology and algorithms"
        description="The approach and models the report describes."
      >
        <div className="space-y-3">
          <ClaimList
            claims={profile.methodology}
            emptyMessage="No methodology description was identified."
          />
          <div>
            <p className="mb-1.5 text-xs font-medium tracking-wide text-muted uppercase">
              Algorithms and models
            </p>
            <ClaimChips claims={profile.algorithms} />
          </div>
        </div>
      </Section>

      <Section
        title="Technology stack"
        description="Languages, frameworks and libraries found in the report."
      >
        <dl className="grid gap-4 sm:grid-cols-2">
          {(
            [
              ["Languages", profile.stack.languages],
              ["Frameworks", profile.stack.frameworks],
              ["Libraries", profile.stack.libraries],
              ["Tools", profile.stack.tools],
            ] as const
          ).map(([label, claims]) => (
            <div key={label}>
              <dt className="mb-1.5 text-xs font-medium tracking-wide text-muted uppercase">
                {label}
              </dt>
              <dd>
                <ClaimChips claims={claims} />
              </dd>
            </div>
          ))}
        </dl>
      </Section>

      <Section
        title="Evaluation"
        description="How the report says the work was measured."
      >
        <div className="space-y-3">
          <div>
            <p className="mb-1.5 text-xs font-medium tracking-wide text-muted uppercase">
              Metrics
            </p>
            <ClaimChips claims={profile.evaluation.metrics} />
          </div>
          {profile.evaluation.validation_strategy && (
            <ClaimView claim={profile.evaluation.validation_strategy} />
          )}
          <ClaimList
            claims={profile.evaluation.reported_results}
            emptyMessage="No reported results were identified."
          />
        </div>
      </Section>

      <Section
        title="Limitations stated in the report"
        description="Weaknesses the authors acknowledged themselves."
      >
        <ClaimList
          claims={profile.stated_limitations}
          emptyMessage="The report does not state any limitations explicitly."
        />
      </Section>

      {profile.extraction_notes.length > 0 && (
        <Section
          title="Extraction notes"
          description="What could not be determined from the document."
        >
          <ul className="list-disc space-y-1 pl-4 text-xs leading-relaxed text-muted">
            {profile.extraction_notes.map((note, index) => (
              <li key={index}>{note}</li>
            ))}
          </ul>
        </Section>
      )}

      <div className="border-t border-border-subtle pt-5">
        <Link href="/upload" className="text-sm text-accent hover:underline">
          Analyse another report
        </Link>
      </div>
    </div>
  );
}
