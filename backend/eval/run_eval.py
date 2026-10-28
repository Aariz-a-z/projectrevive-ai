"""Measure the recommender against the labelled evaluation set.

    cd backend
    ./.venv/Scripts/python.exe -m eval.run_eval        # Windows
    python -m eval.run_eval                            # macOS/Linux

Compares the hybrid engine against the two ablations README section 8 asks
for. Costs nothing and touches no network: the knowledge base, the matching
and the ranking are all local, and the evaluation set supplies profiles
directly rather than extracting them from documents.

The limitations printed with the results are part of the output, not a
disclaimer bolted on. A table of numbers from a ten-case set labelled by one
person is easy to mistake for something stronger.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.knowledge.loader import load_knowledge_base
from app.recommend import baselines
from app.recommend.engine import recommend
from app.schemas.recommendation import UserConstraints
from eval.metrics import (
    catalogue_coverage,
    mean,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)
from eval.schema import EvalCase

DATASET_DIR = Path(__file__).parent / "dataset"
CUTOFFS = (3, 5, 10)

# The evaluation set describes projects, not hardware. A permissive set of
# constraints keeps the comparison about ranking rather than about exclusions
# firing differently for each system.
EVAL_CONSTRAINTS = UserConstraints(
    has_gpu=True,
    dataset_rows=None,
    assumptions=["Evaluation harness: constraints held constant across systems."],
)


def load_cases() -> list[EvalCase]:
    cases: list[EvalCase] = []
    for path in sorted(DATASET_DIR.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        cases.extend(EvalCase.model_validate(item) for item in raw)
    if not cases:
        raise SystemExit(f"no evaluation cases found in {DATASET_DIR}")
    return cases


def _hybrid(case: EvalCase) -> list[str]:
    report = recommend(
        case.project.to_profile(),
        [f.to_finding() for f in case.findings],
        constraints=EVAL_CONSTRAINTS,
        limit=max(CUTOFFS),
    )
    return [r.id for r in report.recommendations]


SYSTEMS = {
    "hybrid": _hybrid,
    "rules-only": lambda case: baselines.rules_only(
        case.project.to_profile(),
        [f.to_finding() for f in case.findings],
        limit=max(CUTOFFS),
    ),
    "content-only": lambda case: baselines.content_only(
        case.project.to_profile(),
        [f.to_finding() for f in case.findings],
        limit=max(CUTOFFS),
    ),
}


@dataclass
class Result:
    system: str
    metrics: dict[str, float]
    per_case: dict[str, list[str]]


def evaluate(cases: list[EvalCase], catalogue_size: int) -> list[Result]:
    results: list[Result] = []

    for name, run in SYSTEMS.items():
        rankings = {case.id: run(case) for case in cases}
        metrics: dict[str, float] = {}

        for k in CUTOFFS:
            metrics[f"P@{k}"] = mean(
                [
                    precision_at_k(rankings[c.id], c.judgments, k)
                    for c in cases
                ]
            )
            metrics[f"NDCG@{k}"] = mean(
                [ndcg_at_k(rankings[c.id], c.judgments, k) for c in cases]
            )

        metrics["Recall@10"] = mean(
            [recall_at_k(rankings[c.id], c.judgments, 10) for c in cases]
        )
        metrics["Coverage@10"] = catalogue_coverage(
            rankings.values(), catalogue_size, 10
        )
        # Reported because precision divides by k: a system returning 6 items
        # cannot exceed 0.6 at P@10 however good those 6 are. Without this
        # column, that structural cap looks like a ranking difference.
        metrics["Items"] = mean([float(len(rankings[c.id])) for c in cases])
        results.append(Result(system=name, metrics=metrics, per_case=rankings))

    return results


def _table(results: list[Result]) -> str:
    columns = list(results[0].metrics)
    width = max(len(r.system) for r in results) + 2

    header = "system".ljust(width) + "".join(c.rjust(12) for c in columns)
    lines = [header, "-" * len(header)]

    best = {c: max(r.metrics[c] for r in results) for c in columns}
    for result in results:
        row = result.system.ljust(width)
        for column in columns:
            value = result.metrics[column]
            marker = "*" if value == best[column] and value > 0 else " "
            row += f"{value:>11.3f}{marker}"
        lines.append(row)

    return "\n".join(lines)


def _verdict(results: list[Result]) -> list[str]:
    """State plainly where the hybrid wins and where it does not."""
    hybrid = next(r for r in results if r.system == "hybrid")
    others = [r for r in results if r.system != "hybrid"]

    wins, losses, ties = [], [], []
    for column in hybrid.metrics:
        if column == "Items":  # a description, not a score
            continue
        best_other = max(o.metrics[column] for o in others)
        value = hybrid.metrics[column]
        if value > best_other + 1e-9:
            wins.append(column)
        elif value < best_other - 1e-9:
            losses.append(f"{column} (best baseline {best_other:.3f})")
        else:
            ties.append(column)

    lines = []
    if wins:
        lines.append(f"Hybrid beats both baselines on: {', '.join(wins)}")
    if ties:
        lines.append(f"Hybrid ties the best baseline on: {', '.join(ties)}")
    if losses:
        lines.append(f"Hybrid LOSES to a baseline on: {', '.join(losses)}")
    else:
        lines.append("Hybrid is not beaten by a baseline on any metric here.")

    # Flag the structural cap wherever a baseline returns fewer items than the
    # largest cutoff, so a precision win is not read as a ranking win.
    for other in others:
        if other.metrics["Items"] < max(CUTOFFS) - 0.5:
            lines.append(
                f"CAVEAT: {other.system} returns {other.metrics['Items']:.1f} "
                f"items on average, so its P@{max(CUTOFFS)} cannot exceed "
                f"{other.metrics['Items'] / max(CUTOFFS):.2f} however well it "
                "ranks. Compare at the smaller cutoffs instead."
            )
    return lines


LIMITATIONS = """\
HOW TO READ THESE NUMBERS

  - {n} cases. That is small enough that one case moving a few places visibly
    shifts every mean. Treat differences under roughly 0.05 as noise.
  - One annotator, who is also the author of the knowledge base being scored.
    The labels and the system share assumptions, so these numbers are biased
    upward and are not evidence of how the system performs for anyone else.
  - No inter-annotator agreement, because there is no second annotator.
  - The evaluation supplies project profiles directly, so nothing here
    measures document extraction. A good score is about ranking only.
  - Relevance is a judgement about appropriateness, not an observed outcome.
    No recommendation here has been implemented and measured.

These are measurements of a ranking against one person's opinion. They are
not evidence that following the recommendations improves a project."""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, help="Write full results here.")
    args = parser.parse_args()

    cases = load_cases()
    catalogue = load_knowledge_base()
    results = evaluate(cases, len(catalogue))

    print(f"\nRecommendation quality: {len(cases)} cases, "
          f"{len(catalogue)} knowledge base entries\n")
    print(_table(results))
    print("\n* best in column\n")
    for line in _verdict(results):
        print(f"  {line}")
    print()
    print(LIMITATIONS.format(n=len(cases)))
    print()

    if args.json:
        payload = {
            "cases": len(cases),
            "catalogue_size": len(catalogue),
            "cutoffs": list(CUTOFFS),
            "results": {
                r.system: {"metrics": r.metrics, "rankings": r.per_case}
                for r in results
            },
            "limitations": LIMITATIONS.format(n=len(cases)),
        }
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Full results written to {args.json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
