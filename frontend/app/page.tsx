import Link from "next/link";

const STEPS = [
  {
    title: "Read the report",
    body: "Extracts text from a PDF or DOCX, keeping page numbers so every finding can cite where it came from.",
  },
  {
    title: "Build a project profile",
    body: "Identifies the problem, methodology, algorithms, dataset, stack and evaluation, separating what the report states from what had to be inferred.",
  },
  {
    title: "Find gaps",
    body: "Looks for missing evaluation, leakage risks, unsuitable metrics, thin feature engineering and absent testing or deployment.",
  },
  {
    title: "Recommend improvements",
    body: "Matches the project against a curated catalogue of improvements, filters by what is actually feasible for you, and ranks what is left.",
  },
  {
    title: "Explain the reasoning",
    body: "Each recommendation carries its evidence, expected benefit, trade-offs, effort and a way to validate it.",
  },
];

export default function Home() {
  return (
    <div className="space-y-12">
      <section className="max-w-2xl space-y-4">
        <p className="text-xs font-medium tracking-widest text-accent uppercase">
          Project analysis and enhancement
        </p>
        <h1 className="text-3xl leading-tight font-semibold tracking-tight sm:text-4xl">
          Work out what to improve in an existing AI/ML project &mdash; and why.
        </h1>
        <p className="text-base leading-relaxed text-muted">
          Upload a project report. ProjectRevive AI reads it, works out what the
          project actually does, identifies where it is weak, and recommends
          specific improvements with the reasoning, trade-offs and effort for
          each one.
        </p>
        <div className="flex flex-wrap items-center gap-3 pt-2">
          <Link
            href="/upload"
            className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90 dark:text-[#10201c]"
          >
            Analyse a report
          </Link>
          <span className="text-xs text-muted">PDF or DOCX</span>
        </div>
      </section>

      <section className="space-y-4">
        <h2 className="text-base font-semibold tracking-tight">
          How it works
        </h2>
        <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {STEPS.map((step, index) => (
            <li
              key={step.title}
              className="rounded-md border border-border-subtle bg-surface p-4"
            >
              <p className="font-mono text-xs text-muted">
                {String(index + 1).padStart(2, "0")}
              </p>
              <h3 className="mt-1.5 text-sm font-semibold">{step.title}</h3>
              <p className="mt-1 text-xs leading-relaxed text-muted">
                {step.body}
              </p>
            </li>
          ))}
        </ol>
      </section>

      <section className="max-w-2xl space-y-3 rounded-md border border-border-subtle bg-surface-muted p-5">
        <h2 className="text-sm font-semibold tracking-tight">
          What this tool will and will not claim
        </h2>
        <ul className="space-y-2 text-xs leading-relaxed text-muted">
          <li>
            Every extracted fact is marked either as stated in your report, with
            a page citation you can open and check, or as an inference, with the
            reasoning behind it.
          </li>
          <li>
            A citation that cannot be matched back to the page it claims is
            rejected rather than shown, and the analysis says so.
          </li>
          <li>
            Recommendation scores are a transparent weighted formula, not a
            validated scientific measurement. Expected benefits are labelled as
            expectations until an experiment supports them.
          </li>
          <li>
            Nothing here reports accuracy or improvement figures that were not
            measured.
          </li>
        </ul>
      </section>
    </div>
  );
}
