import Link from "next/link";

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
import { Badge, Panel, PanelHeader, type Accent } from "@/components/ui";

const FEATURES: {
  icon: React.ReactNode;
  accent: Accent;
  title: string;
  body: string;
  ready: boolean;
}[] = [
  {
    icon: <IconSearch />,
    accent: "cyan",
    title: "Structured report analysis",
    body: "Pulls the problem, methodology, algorithms, dataset, stack and evaluation out of a PDF or DOCX.",
    ready: true,
  },
  {
    icon: <IconQuote />,
    accent: "green",
    title: "Verified page citations",
    body: "Every stated finding carries a page number and a verbatim quote, checked against that page before you see it.",
    ready: true,
  },
  {
    icon: <IconShield />,
    accent: "violet",
    title: "Fact and inference separated",
    body: "What the report says is never blended with what the system guessed. Each is labelled and counted.",
    ready: true,
  },
  {
    icon: <IconCode />,
    accent: "blue",
    title: "Tech stack detection",
    body: "Identifies the languages, frameworks and libraries the report names, each traced to where it appears.",
    ready: true,
  },
  {
    icon: <IconAlert />,
    accent: "amber",
    title: "Weakness and gap analysis",
    body: "Finds missing evaluation, leakage risk, unsuitable metrics and absent testing.",
    ready: false,
  },
  {
    icon: <IconLayers />,
    accent: "cyan",
    title: "Ranked recommendations",
    body: "Matches your project against a catalogue of improvements, filtered by what is actually feasible for you.",
    ready: false,
  },
  {
    icon: <IconBook />,
    accent: "violet",
    title: "Architecture and roadmap",
    body: "A proposed architecture diagram and a phased plan, generated from structured data rather than prose.",
    ready: false,
  },
  {
    icon: <IconExport />,
    accent: "green",
    title: "Exportable report",
    body: "Download the full improvement report with evidence, trade-offs and a testing plan.",
    ready: false,
  },
];

function PreviewMock() {
  return (
    <Panel className="overflow-hidden">
      <PanelHeader
        title="Analysis overview"
        icon={<IconSearch />}
        right={<Badge accent="green">Verified</Badge>}
      />
      <div className="space-y-3 p-4">
        <div className="panel-inset rounded-lg p-3">
          <p className="text-[11px] tracking-wide text-muted uppercase">
            Project
          </p>
          <p className="mt-1 text-sm font-semibold">
            Handwritten Digit Recognition Using Deep Learning
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <Badge accent="cyan">computer vision</Badge>
            <Badge accent="green">CNN · p3</Badge>
            <Badge accent="green">TensorFlow · p3</Badge>
            <Badge accent="green">accuracy · p4</Badge>
          </div>
        </div>

        <div className="panel-inset rounded-lg p-3">
          <div className="flex items-center justify-between text-[11px] text-muted">
            <span>Evidence coverage</span>
            <span className="font-mono">16 stated · 1 inferred</span>
          </div>
          <div className="mt-2 flex h-1.5 overflow-hidden rounded-full bg-[#0a1222]">
            <div className="bg-green" style={{ width: "94%" }} />
            <div className="bg-amber" style={{ width: "6%" }} />
          </div>
        </div>

        <div className="panel-inset rounded-lg border-l-2 border-l-green p-3">
          <p className="text-[11px] text-muted">Page 3</p>
          <p className="mt-1 text-xs leading-relaxed text-fg-dim italic">
            &ldquo;We implemented a CNN in Python using TensorFlow and
            Keras.&rdquo;
          </p>
        </div>
      </div>
    </Panel>
  );
}

export default function Home() {
  return (
    <div className="space-y-16">
      <section className="grid items-center gap-10 lg:grid-cols-[1.05fr_0.95fr]">
        <div className="space-y-5">
          <div className="flex flex-wrap gap-2">
            <Badge accent="cyan">PDF &amp; DOCX</Badge>
            <Badge accent="green">Citation-verified</Badge>
            <Badge accent="violet">MIT licensed</Badge>
          </div>

          <h1 className="text-4xl leading-[1.08] font-semibold tracking-tight sm:text-5xl">
            Understand any project report.{" "}
            <span className="grad-text">With receipts.</span>
          </h1>

          <p className="max-w-xl text-base leading-relaxed text-fg-dim">
            ProjectRevive AI reads an existing AI/ML project report, works out
            what the project actually does, and shows you where it is weak
            &mdash; with every finding traced back to the page it came from.
          </p>

          <div className="flex flex-wrap items-center gap-3 pt-1">
            <Link
              href="/signup"
              className="rounded-lg bg-gradient-to-r from-cyan to-blue px-5 py-2.5 text-sm font-semibold text-[#04121c] hover:brightness-110"
            >
              Create a free account
            </Link>
            <Link
              href="/login"
              className="rounded-lg border border-edge-bright bg-panel-inset px-5 py-2.5 text-sm text-fg-dim hover:border-cyan/40 hover:text-fg"
            >
              Sign in
            </Link>
          </div>

          <p className="text-xs text-muted">
            No fabricated metrics. If a number was not measured, it is labelled
            an estimate.
          </p>
        </div>

        <PreviewMock />
      </section>

      <section className="space-y-5">
        <div className="flex items-end justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold tracking-tight">
              What it does
            </h2>
            <p className="mt-1 text-sm text-muted">
              Shipped features are marked live. The rest are being built and are
              listed so you know what is coming, not to imply they already work.
            </p>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map((feature) => (
            <Panel key={feature.title} className="flex flex-col gap-2.5 p-4">
              <div className="flex items-start justify-between gap-2">
                <span
                  className={`grid h-9 w-9 place-items-center rounded-lg bg-panel-inset p-2 ring-1 ring-edge ${
                    { cyan: "text-cyan", blue: "text-blue", violet: "text-violet", green: "text-green", amber: "text-amber", rose: "text-rose" }[feature.accent]
                  }`}
                >
                  {feature.icon}
                </span>
                {feature.ready ? (
                  <Badge accent="green">Live</Badge>
                ) : (
                  <Badge accent="amber">Planned</Badge>
                )}
              </div>
              <h3 className="text-sm font-semibold">{feature.title}</h3>
              <p className="text-xs leading-relaxed text-muted">
                {feature.body}
              </p>
            </Panel>
          ))}
        </div>
      </section>

      <section className="grid gap-3 sm:grid-cols-3">
        {[
          {
            n: "01",
            t: "Create an account",
            b: "Your analyses are private to you and saved so you can come back to them.",
          },
          {
            n: "02",
            t: "Upload a report",
            b: "PDF or DOCX. The file is processed in memory and never written to disk.",
          },
          {
            n: "03",
            t: "Read the evidence",
            b: "Open any finding to see the page and the exact sentence it came from.",
          },
        ].map((step) => (
          <Panel key={step.n} className="p-5">
            <p className="font-mono text-xs text-cyan">{step.n}</p>
            <h3 className="mt-2 text-sm font-semibold">{step.t}</h3>
            <p className="mt-1.5 text-xs leading-relaxed text-muted">{step.b}</p>
          </Panel>
        ))}
      </section>
    </div>
  );
}
