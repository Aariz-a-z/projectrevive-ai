"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { ClaimChips, ClaimList, ClaimView } from "@/components/ClaimView";
import { FindingCard } from "@/components/FindingCard";
import {
  IconAlert,
  IconBook,
  IconCode,
  IconExport,
  IconLayers,
  IconQuote,
  IconSearch,
  IconShield,
} from "@/components/icons";
import { MermaidDiagram } from "@/components/MermaidDiagram";
import { RecommendationCard } from "@/components/RecommendationCard";
import { StackList } from "@/components/StackList";
import {
  Badge,
  Notice,
  Panel,
  PanelHeader,
  Section,
  StatTile,
} from "@/components/ui";
import { ApiError, getAnalysis } from "@/lib/api";
import type { AnalysisDetail, Claim, ProjectProfile } from "@/lib/types";

import { AnalysisSkeleton } from "./Skeleton";

const TABS = [
  { id: "overview", label: "Overview", icon: <IconSearch /> },
  { id: "stack", label: "Tech Stack", icon: <IconCode /> },
  { id: "architecture", label: "Architecture", icon: <IconLayers /> },
  { id: "evaluation", label: "Evaluation", icon: <IconShield /> },
  { id: "findings", label: "Findings", icon: <IconAlert /> },
  { id: "recommendations", label: "Recommendations", icon: <IconLayers /> },
  { id: "roadmap", label: "Roadmap", icon: <IconBook /> },
  { id: "evidence", label: "Evidence", icon: <IconQuote /> },
  { id: "export", label: "Export", icon: <IconExport /> },
] as const;

type TabId = (typeof TABS)[number]["id"];

/** Mirrors ProjectProfile.all_claims() on the backend. */
function allClaims(profile: ProjectProfile): Claim[] {
  const optional = [
    profile.dataset.name,
    profile.dataset.size,
    profile.dataset.source,
    profile.evaluation.validation_strategy,
    profile.architecture_description,
  ].filter((c): c is Claim => c !== null);

  return [
    profile.title,
    profile.domain,
    profile.problem_statement,
    ...profile.objectives,
    ...profile.intended_users,
    ...profile.methodology,
    ...profile.algorithms,
    ...profile.stated_limitations,
    ...profile.stack.languages,
    ...profile.stack.frameworks,
    ...profile.stack.libraries,
    ...profile.stack.tools,
    ...profile.dataset.preprocessing,
    ...profile.evaluation.metrics,
    ...profile.evaluation.reported_results,
    ...optional,
  ];
}

function CoverageBar({ analysis }: { analysis: AnalysisDetail }) {
  const { stated, inferred, total } = analysis.claim_counts;
  const pct = total > 0 ? Math.round((stated / total) * 100) : 0;

  return (
    <div>
      <div className="flex items-baseline justify-between text-xs">
        <span className="text-muted">Evidence coverage</span>
        <span className="font-mono text-fg-dim">{pct}% cited</span>
      </div>
      <div
        className="mt-2 flex h-2 overflow-hidden rounded-full bg-panel-inset"
        role="img"
        aria-label={`${stated} of ${total} findings are stated in the report; ${inferred} are inferred.`}
      >
        <div className="bg-green" style={{ width: `${pct}%` }} />
        <div className="bg-amber" style={{ width: `${100 - pct}%` }} />
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-full bg-green" />
          {stated} stated in the report
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-full bg-amber" />
          {inferred} inferred
        </span>
      </div>
    </div>
  );
}

export function AnalysisView() {
  const { id } = useParams<{ id: string }>();
  const [analysis, setAnalysis] = useState<AnalysisDetail | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [tab, setTab] = useState<TabId>("overview");

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

  const byPage = useMemo(() => {
    if (!analysis) return [];
    const map = new Map<number, { claim: Claim; quote: string }[]>();
    for (const claim of allClaims(analysis.profile)) {
      for (const item of claim.evidence) {
        const list = map.get(item.page) ?? [];
        list.push({ claim, quote: item.quote });
        map.set(item.page, list);
      }
    }
    return [...map.entries()].sort((a, b) => a[0] - b[0]);
  }, [analysis]);

  if (error) {
    return (
      <div className="mx-auto max-w-lg space-y-4 py-10">
        <Notice
          tone={error.isAuthError ? "caution" : "error"}
          title={
            error.isAuthError
              ? "You need to sign in"
              : "This analysis could not be loaded"
          }
        >
          {error.message}
        </Notice>
        <Link
          href={error.isAuthError ? "/login" : "/dashboard"}
          className="inline-block text-sm text-cyan hover:underline"
        >
          {error.isAuthError ? "Go to sign in" : "Back to dashboard"}
        </Link>
      </div>
    );
  }

  if (!analysis) return <AnalysisSkeleton />;

  const { profile } = analysis;

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0 space-y-1.5">
          <p className="font-mono text-[11px] text-muted">
            {analysis.filename} · {analysis.page_count} pages ·{" "}
            {new Date(analysis.created_at).toLocaleString()}
          </p>
          <h1 className="text-2xl leading-tight font-semibold tracking-tight">
            {profile.title.value}
          </h1>
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge accent="cyan">{profile.domain.value}</Badge>
            {analysis.provenance.is_mock && <Badge accent="amber">mock provider</Badge>}
            <span className="font-mono text-[11px] text-muted">
              {analysis.provenance.model}
            </span>
          </div>
        </div>
        <Link
          href="/dashboard"
          className="rounded-lg border border-edge-bright bg-panel-inset px-3 py-1.5 text-sm text-fg-dim hover:border-cyan/40 hover:text-fg"
        >
          Back to dashboard
        </Link>
      </header>

      {analysis.provenance.is_mock && (
        <Notice tone="caution" title="No language model is configured">
          The <strong>project profile</strong> below came from keyword matching
          rather than comprehension, so treat it as a structural demonstration.
          The <strong>weaknesses and gaps</strong> are different: those come
          from deterministic rules that need no model, and are as valid here as
          they would be with one. A model would add judgements the rules cannot
          make.
        </Notice>
      )}

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <StatTile value={analysis.page_count} label="Pages read" accent="blue" />
        <StatTile value={analysis.claim_counts.total} label="Findings" accent="cyan" />
        <StatTile
          value={analysis.claim_counts.stated}
          label="With citations"
          accent="green"
        />
        <StatTile
          value={analysis.claim_counts.inferred}
          label="Inferred"
          accent="amber"
        />
      </div>

      <div
        role="tablist"
        aria-label="Analysis sections"
        className="flex flex-wrap gap-1 rounded-xl border border-edge bg-panel-inset p-1"
      >
        {TABS.map((item) => {
          const active = tab === item.id;
          return (
            <button
              key={item.id}
              role="tab"
              aria-selected={active}
              onClick={() => setTab(item.id)}
              className={`flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm transition-colors ${
                active
                  ? "bg-panel-raised font-medium text-fg shadow-sm ring-1 ring-edge-bright"
                  : "text-muted hover:text-fg-dim"
              }`}
            >
              <span className={`h-4 w-4 ${active ? "text-cyan" : ""}`}>
                {item.icon}
              </span>
              {item.label}
            </button>
          );
        })}
      </div>

      {tab === "overview" && (
        <div className="grid gap-5 lg:grid-cols-[1.4fr_0.6fr]">
          <Panel>
            <PanelHeader title="Problem statement" icon={<IconSearch />} />
            <div className="p-4">
              <ClaimView claim={profile.problem_statement} />
            </div>
          </Panel>

          <div className="space-y-5">
            <Panel>
              <PanelHeader
                title="Where this came from"
                icon={<IconShield />}
                accent="green"
              />
              <div className="space-y-3 p-4">
                <CoverageBar analysis={analysis} />
                <dl className="space-y-1.5 border-t border-edge pt-3 text-xs">
                  <div className="flex justify-between gap-2">
                    <dt className="text-muted">Provider</dt>
                    <dd className="font-mono text-fg-dim">
                      {analysis.provenance.provider}
                    </dd>
                  </div>
                  {analysis.provenance.usage.input_tokens > 0 && (
                    <div className="flex justify-between gap-2">
                      <dt className="text-muted">Tokens</dt>
                      <dd className="font-mono text-fg-dim">
                        {analysis.provenance.usage.input_tokens.toLocaleString()} in
                        {" / "}
                        {analysis.provenance.usage.output_tokens.toLocaleString()} out
                      </dd>
                    </div>
                  )}
                </dl>
              </div>
            </Panel>

            {analysis.warnings.length > 0 && (
              <Panel>
                <PanelHeader
                  title="Caveats"
                  icon={<IconAlert />}
                  accent="amber"
                  right={<Badge accent="amber">{analysis.warnings.length}</Badge>}
                />
                <ul className="space-y-2 p-4 text-xs leading-relaxed text-muted">
                  {analysis.warnings.map((warning, index) => (
                    <li key={index} className="border-l-2 border-amber pl-3">
                      {warning}
                    </li>
                  ))}
                </ul>
              </Panel>
            )}
          </div>
        </div>
      )}

      {tab === "stack" && (
        <div className="grid gap-5 lg:grid-cols-[1.5fr_0.5fr]">
          <Panel>
            <PanelHeader
              title="Current versus proposed"
              icon={<IconCode />}
              accent="blue"
            />
            <div className="space-y-5 p-4">
              <Section
                title="Keep"
                description="Used by the project, with no reason found to change it. A verdict, not an omission."
              >
                <StackList
                  entries={analysis.comparison.entries.filter(
                    (e) => e.verdict === "keep",
                  )}
                  empty="Nothing in the report could be attributed to a specific technology."
                />
              </Section>

              <Section
                title="Add"
                description="Introduced by a recommendation. Each one names which."
              >
                <StackList
                  entries={analysis.comparison.entries.filter(
                    (e) => e.verdict === "add",
                  )}
                  empty="The recommendations need nothing the project does not already use."
                />
              </Section>

              {analysis.comparison.entries.some(
                (e) => e.verdict === "replace",
              ) && (
                <Section title="Replace">
                  <StackList
                    entries={analysis.comparison.entries.filter(
                      (e) => e.verdict === "replace",
                    )}
                    empty=""
                  />
                </Section>
              )}
            </div>
          </Panel>

          <div className="space-y-5">
            <Panel>
              <PanelHeader
                title="Algorithms in the report"
                icon={<IconSearch />}
              />
              <div className="p-4">
                <ClaimChips claims={profile.algorithms} />
              </div>
            </Panel>

            <Panel>
              <PanelHeader
                title="How this was decided"
                icon={<IconShield />}
                accent="violet"
              />
              <ul className="space-y-2 p-4 text-[11px] leading-relaxed text-muted">
                {analysis.comparison.notes.map((note, index) => (
                  <li key={index} className="border-l-2 border-violet pl-3">
                    {note}
                  </li>
                ))}
              </ul>
            </Panel>
          </div>
        </div>
      )}

      {tab === "architecture" && (
        <div className="space-y-5">
          {!analysis.architecture ? (
            <Notice tone="info" title="No architecture was generated">
              This analysis predates the architecture view. Re-run it to
              generate one.
            </Notice>
          ) : (
            <>
              <div className="grid gap-5 lg:grid-cols-2">
                <Panel>
                  <PanelHeader
                    title="As described in the report"
                    icon={<IconLayers />}
                  />
                  <div className="p-4">
                    <MermaidDiagram
                      chart={analysis.architecture.current_mermaid}
                      ariaLabel="Architecture described in the report"
                    />
                  </div>
                </Panel>

                <Panel>
                  <PanelHeader
                    title="With the recommendations applied"
                    icon={<IconLayers />}
                    accent="green"
                    right={
                      analysis.architecture.proposed.nodes.some(
                        (n) => n.origin === "proposed",
                      ) ? (
                        <Badge accent="green">
                          +
                          {
                            analysis.architecture.proposed.nodes.filter(
                              (n) => n.origin === "proposed",
                            ).length
                          }
                        </Badge>
                      ) : undefined
                    }
                  />
                  <div className="p-4">
                    <MermaidDiagram
                      chart={analysis.architecture.proposed_mermaid}
                      ariaLabel="Architecture with the recommendations applied"
                    />
                  </div>
                </Panel>
              </div>

              <Panel>
                <PanelHeader
                  title="Reading these diagrams"
                  icon={<IconShield />}
                  accent="violet"
                />
                <ul className="space-y-2 p-4 text-[11px] leading-relaxed text-muted">
                  {analysis.architecture.notes.map((note, index) => (
                    <li key={index} className="border-l-2 border-violet pl-3">
                      {note}
                    </li>
                  ))}
                </ul>
              </Panel>
            </>
          )}
        </div>
      )}

      {tab === "evaluation" && (
        <Panel>
          <PanelHeader title="Evaluation" icon={<IconShield />} accent="green" />
          <div className="space-y-5 p-4">
            <Section
              title="Metrics"
              description="How the report says the work was measured."
            >
              <ClaimChips claims={profile.evaluation.metrics} />
            </Section>
            {profile.evaluation.validation_strategy && (
              <Section title="Validation strategy">
                <ClaimView claim={profile.evaluation.validation_strategy} />
              </Section>
            )}
            <Section title="Reported results">
              <ClaimList
                claims={profile.evaluation.reported_results}
                emptyMessage="No reported results were identified in this document."
              />
            </Section>
          </div>
        </Panel>
      )}

      {tab === "findings" && (
        <div className="grid gap-5 lg:grid-cols-[1.5fr_0.5fr]">
          <Panel>
            <PanelHeader
              title="Weaknesses and gaps"
              icon={<IconAlert />}
              accent="rose"
              right={
                <Badge accent="rose">{analysis.findings.findings.length}</Badge>
              }
            />
            <div className="space-y-3 p-4">
              {analysis.findings.findings.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted">
                  No weaknesses or gaps were detected in this report.
                </p>
              ) : (
                analysis.findings.findings.map((finding, index) => (
                  <FindingCard key={`${finding.title}-${index}`} finding={finding} />
                ))
              )}
            </div>
          </Panel>

          <div className="space-y-5">
            <Panel>
              <PanelHeader title="Severity" icon={<IconAlert />} accent="amber" />
              <div className="space-y-2 p-4">
                {(
                  [
                    ["high", "rose", "May invalidate the results"],
                    ["medium", "amber", "Limits usefulness"],
                    ["low", "cyan", "Worth improving"],
                  ] as const
                ).map(([key, accent, caption]) => (
                  <div
                    key={key}
                    className="flex items-center justify-between gap-3"
                  >
                    <div className="min-w-0">
                      <p className="text-xs font-medium capitalize">{key}</p>
                      <p className="truncate text-[11px] text-muted">{caption}</p>
                    </div>
                    <Badge accent={accent}>
                      {analysis.finding_counts?.[key] ?? 0}
                    </Badge>
                  </div>
                ))}

                <div className="mt-3 border-t border-edge pt-3 text-[11px] text-muted">
                  <p className="flex justify-between">
                    <span>From deterministic rules</span>
                    <span className="font-mono text-green">
                      {analysis.finding_sources?.rule ?? 0}
                    </span>
                  </p>
                  <p className="mt-1 flex justify-between">
                    <span>From the model</span>
                    <span className="font-mono text-amber">
                      {analysis.finding_sources?.model ?? 0}
                    </span>
                  </p>
                  <p className="mt-2 leading-relaxed">
                    Rule findings can be read and checked in the source. Model
                    findings are judgements worth verifying yourself.
                  </p>
                </div>
              </div>
            </Panel>

            <Panel>
              <PanelHeader
                title="Stated by the authors"
                icon={<IconQuote />}
                accent="violet"
              />
              <div className="p-4">
                <ClaimList
                  claims={profile.stated_limitations}
                  emptyMessage="The report does not state any limitations explicitly."
                />
              </div>
            </Panel>

            {analysis.findings.notes.length > 0 && (
              <Panel>
                <PanelHeader
                  title="Analysis notes"
                  icon={<IconSearch />}
                  accent="violet"
                />
                <ul className="space-y-2 p-4 text-[11px] leading-relaxed text-muted">
                  {analysis.findings.notes.map((note, index) => (
                    <li key={index} className="border-l-2 border-violet pl-3">
                      {note}
                    </li>
                  ))}
                </ul>
              </Panel>
            )}
          </div>
        </div>
      )}

      {tab === "recommendations" && (
        <div className="grid gap-5 lg:grid-cols-[1.55fr_0.45fr]">
          <Panel>
            <PanelHeader
              title="Ranked improvements"
              icon={<IconLayers />}
              accent="cyan"
              right={
                <Badge accent="cyan">
                  {analysis.recommendations.recommendations.length}
                </Badge>
              }
            />
            <div className="space-y-3 p-4">
              {analysis.recommendations.recommendations.length === 0 ? (
                <p className="py-8 text-center text-sm text-muted">
                  No recommendations were produced for this report.
                </p>
              ) : (
                analysis.recommendations.recommendations.map((item, index) => (
                  <RecommendationCard
                    key={item.id}
                    recommendation={item}
                    rank={index + 1}
                  />
                ))
              )}
            </div>
          </Panel>

          <div className="space-y-5">
            <Panel>
              <PanelHeader
                title="How this was ranked"
                icon={<IconShield />}
                accent="violet"
              />
              <div className="space-y-2 p-4 text-[11px] leading-relaxed text-muted">
                <p className="font-mono text-fg-dim">
                  {Object.entries(analysis.recommendations.weights)
                    .map(([k, v]) => `${v}×${k}`)
                    .join(" + ")}
                </p>
                {analysis.recommendations.notes.map((note, index) => (
                  <p key={index}>{note}</p>
                ))}
              </div>
            </Panel>

            <Panel>
              <PanelHeader
                title="Assumptions made"
                icon={<IconAlert />}
                accent="amber"
              />
              <ul className="space-y-2 p-4 text-[11px] leading-relaxed text-muted">
                {analysis.recommendations.constraints.assumptions.map(
                  (item, index) => (
                    <li key={index} className="border-l-2 border-amber pl-3">
                      {item}
                    </li>
                  ),
                )}
              </ul>
            </Panel>

            {analysis.recommendations.excluded.length > 0 && (
              <Panel>
                <PanelHeader
                  title="Ruled out"
                  icon={<IconAlert />}
                  accent="rose"
                  right={
                    <Badge accent="rose">
                      {analysis.recommendations.excluded.length}
                    </Badge>
                  }
                />
                <ul className="space-y-2 p-4 text-[11px] leading-relaxed text-muted">
                  {analysis.recommendations.excluded.map((item, index) => (
                    <li key={index} className="border-l-2 border-rose pl-3">
                      {item}
                    </li>
                  ))}
                </ul>
              </Panel>
            )}
          </div>
        </div>
      )}

      {tab === "roadmap" && (
        <div className="grid gap-5 lg:grid-cols-[1.55fr_0.45fr]">
          <div className="space-y-4">
            {analysis.roadmap.phases.length === 0 ? (
              <Panel>
                <div className="p-8 text-center text-sm text-muted">
                  No recommendations were produced, so there is no plan.
                </div>
              </Panel>
            ) : (
              analysis.roadmap.phases.map((phase) => (
                <Panel key={phase.id}>
                  <PanelHeader
                    title={`Phase ${phase.order}: ${phase.title}`}
                    icon={<IconBook />}
                    accent={phase.order === 1 ? "green" : "cyan"}
                    right={<Badge accent="cyan">{phase.tasks.length}</Badge>}
                  />
                  <div className="space-y-3 p-4">
                    <p className="border-l-2 border-cyan pl-3 text-xs leading-relaxed text-muted italic">
                      {phase.rationale}
                    </p>
                    <ol className="space-y-2">
                      {phase.tasks.map((task) => (
                        <li
                          key={task.recommendation_id}
                          className="panel-inset rounded-lg p-3"
                        >
                          <div className="flex flex-wrap items-start justify-between gap-2">
                            <p className="text-sm font-medium">{task.title}</p>
                            <Badge
                              accent={
                                task.complexity === "low"
                                  ? "green"
                                  : task.complexity === "medium"
                                    ? "amber"
                                    : "rose"
                              }
                            >
                              {task.complexity}
                            </Badge>
                          </div>
                          <p className="mt-1.5 text-xs leading-relaxed text-muted">
                            <span className="text-fg-dim">Done when:</span>{" "}
                            {task.validation}
                          </p>
                          {task.dependencies.length > 0 && (
                            <p className="mt-1.5 font-mono text-[10px] text-muted">
                              needs {task.dependencies.join(", ")}
                            </p>
                          )}
                        </li>
                      ))}
                    </ol>
                  </div>
                </Panel>
              ))
            )}
          </div>

          <div className="space-y-5">
            <Panel>
              <PanelHeader title="Effort" icon={<IconShield />} accent="violet" />
              <div className="space-y-2 p-4">
                {(["low", "medium", "high"] as const).map((level) => {
                  const count = analysis.roadmap.phases
                    .flatMap((p) => p.tasks)
                    .filter((t) => t.complexity === level).length;
                  return (
                    <div
                      key={level}
                      className="flex items-center justify-between text-xs"
                    >
                      <span className="text-muted capitalize">{level}</span>
                      <span className="font-mono text-fg-dim">{count}</span>
                    </div>
                  );
                })}
              </div>
            </Panel>

            <Panel>
              <PanelHeader
                title="About this plan"
                icon={<IconAlert />}
                accent="amber"
              />
              <ul className="space-y-2 p-4 text-[11px] leading-relaxed text-muted">
                {analysis.roadmap.notes.map((note, index) => (
                  <li key={index} className="border-l-2 border-amber pl-3">
                    {note}
                  </li>
                ))}
              </ul>
            </Panel>
          </div>
        </div>
      )}

      {tab === "export" && (
        <div className="mx-auto max-w-2xl space-y-5">
          <Panel>
            <PanelHeader
              title="Download the improvement report"
              icon={<IconExport />}
              accent="green"
            />
            <div className="space-y-4 p-5">
              <p className="text-sm leading-relaxed text-fg-dim">
                Everything in this analysis as a single Markdown file: the
                project summary, the methodology, every finding with its
                evidence, the ranked recommendations with their trade-offs, the
                stack comparison, both architecture diagrams, the roadmap and
                a testing plan — followed by exactly what was assumed and what
                has not been measured.
              </p>

              <ol className="space-y-1.5 text-xs text-muted">
                {[
                  "Original project summary",
                  "Extracted methodology",
                  "Identified weaknesses and gaps",
                  "Ranked recommendations",
                  "Technology comparison",
                  "Proposed architecture",
                  "Development roadmap",
                  "Testing and evaluation plan",
                  "Assumptions and limitations",
                ].map((section, index) => (
                  <li key={section} className="flex gap-2">
                    <span className="font-mono text-cyan">{index + 1}.</span>
                    {section}
                  </li>
                ))}
              </ol>

              <div className="flex flex-wrap items-center gap-3 pt-1">
                <a
                  href={`/api/analyses/${analysis.id}/report.md`}
                  download
                  className="inline-flex items-center gap-2 rounded-lg bg-gradient-to-r from-cyan to-blue px-4 py-2 text-sm font-semibold text-[#04121c] hover:brightness-110"
                >
                  <IconExport className="h-4 w-4" />
                  Download Markdown
                </a>
                <span className="text-xs text-muted">
                  Renders on GitHub, converts with pandoc, prints from any
                  editor.
                </span>
              </div>
            </div>
          </Panel>

          <Notice tone="info" title="Why Markdown rather than PDF">
            A PDF would need a rendering toolchain this service does not
            otherwise use, and would be harder to diff, edit or paste into
            your own report. The Mermaid diagrams render natively on GitHub.
          </Notice>
        </div>
      )}

      {tab === "evidence" && (
        <Panel>
          <PanelHeader
            title="Evidence by page"
            icon={<IconQuote />}
            accent="green"
            right={
              <Badge accent="green">
                {byPage.reduce((sum, [, items]) => sum + items.length, 0)} quotes
              </Badge>
            }
          />
          <div className="p-4">
            {byPage.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted">
                No citations were recorded for this document.
              </p>
            ) : (
              <ol className="space-y-4">
                {byPage.map(([page, items]) => (
                  <li key={page}>
                    <p className="mb-2 font-mono text-[11px] tracking-wide text-cyan uppercase">
                      page {page}
                    </p>
                    <ul className="space-y-2">
                      {items.map((item, index) => (
                        <li
                          key={index}
                          className="panel-inset rounded-lg border-l-2 border-l-green p-3"
                        >
                          <p className="text-xs font-medium text-fg-dim">
                            {item.claim.value}
                          </p>
                          <blockquote className="mt-1 text-xs leading-relaxed text-muted italic">
                            &ldquo;{item.quote}&rdquo;
                          </blockquote>
                        </li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ol>
            )}
          </div>
        </Panel>
      )}
    </div>
  );
}
