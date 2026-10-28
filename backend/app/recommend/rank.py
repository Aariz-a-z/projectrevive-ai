"""Feasibility, hard constraints, and the hybrid score.

The formula is README section 7's, with the weights configurable:

    raw = w1·relevance + w2·feasibility + w3·impact − w4·effort − w5·cost

Section 7 also requires components to be normalised to a documented scale
before combining. Each component is already in [0, 1], but the weighted sum is
not: its range is [−(w4+w5), w1+w2+w3], which shifts whenever the weights are
changed. `final` is therefore rescaled from that range onto [0, 1], so two
runs with different weights stay comparable and a score of 0.8 means the same
thing in both.

Hard constraints are not a low score. README section 7 is specific that a
solution needing hardware the user does not have should not rank highly, and
the honest form of that is exclusion with a stated reason rather than a
recommendation they cannot act on sitting lower down a list.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.knowledge.schema import KBEntry
from app.recommend.matching import Candidate
from app.schemas.recommendation import (
    COMPLEXITY_EFFORT,
    COST_PENALTY,
    CostBand,
    ScoreBreakdown,
    SkillLevel,
    UserConstraints,
    Weights,
)

SKILL_ORDER = {
    SkillLevel.BEGINNER: 0,
    SkillLevel.INTERMEDIATE: 1,
    SkillLevel.ADVANCED: 2,
}
COST_ORDER = {
    CostBand.NONE: 0,
    CostBand.LOW: 1,
    CostBand.MEDIUM: 2,
    CostBand.HIGH: 3,
}


@dataclass
class Feasibility:
    score: float
    notes: list[str] = field(default_factory=list)
    excluded_reason: str | None = None

    @property
    def is_possible(self) -> bool:
        return self.excluded_reason is None


def assess_feasibility(entry: KBEntry, constraints: UserConstraints) -> Feasibility:
    """Whether this project can actually adopt the entry, and at what cost."""
    notes: list[str] = []

    if entry.requires_gpu and not constraints.has_gpu:
        return Feasibility(
            score=0.0,
            excluded_reason=(
                "needs a GPU, and none was identified as available for this "
                "project"
            ),
        )

    if (
        entry.min_dataset_rows is not None
        and constraints.dataset_rows is not None
        and constraints.dataset_rows < entry.min_dataset_rows
    ):
        return Feasibility(
            score=0.0,
            excluded_reason=(
                f"needs at least {entry.min_dataset_rows:,} rows, and this "
                f"project appears to have about {constraints.dataset_rows:,}"
            ),
        )

    score = 1.0

    skill_gap = SKILL_ORDER[entry.skill_level] - SKILL_ORDER[constraints.skill_level]
    if skill_gap == 1:
        score -= 0.2
        notes.append(
            f"Assumes {entry.skill_level.value} familiarity, one step above "
            f"the assumed {constraints.skill_level.value} level."
        )
    elif skill_gap >= 2:
        score -= 0.4
        notes.append(
            f"Assumes {entry.skill_level.value} familiarity, well above the "
            f"assumed {constraints.skill_level.value} level."
        )

    cost_gap = COST_ORDER[entry.cost] - COST_ORDER[constraints.budget]
    if cost_gap == 1:
        score -= 0.15
        notes.append(
            f"Costs more ({entry.cost.value}) than the assumed "
            f"{constraints.budget.value} budget."
        )
    elif cost_gap >= 2:
        score -= 0.35
        notes.append(
            f"Costs considerably more ({entry.cost.value}) than the assumed "
            f"{constraints.budget.value} budget."
        )

    if not constraints.needs_deployment and entry.category.value in {
        "deployment",
        "scalability",
    }:
        score -= 0.25
        notes.append(
            "Concerns deployment, which this project does not appear to need."
        )

    return Feasibility(score=max(0.0, min(1.0, score)), notes=notes)


def score_candidate(
    candidate: Candidate,
    constraints: UserConstraints,
    weights: Weights,
) -> tuple[ScoreBreakdown, Feasibility]:
    """Produce the full breakdown. Caller checks `feasibility.is_possible`."""
    entry = candidate.entry
    feasibility = assess_feasibility(entry, constraints)

    relevance = candidate.relevance
    impact = entry.impact
    effort = COMPLEXITY_EFFORT[entry.complexity]
    cost = COST_PENALTY[entry.cost]

    raw = (
        weights.relevance * relevance
        + weights.feasibility * feasibility.score
        + weights.impact * impact
        - weights.effort * effort
        - weights.cost * cost
    )

    # Documented rescale: map the weight-dependent range onto [0, 1].
    lowest = -(weights.effort + weights.cost)
    highest = weights.relevance + weights.feasibility + weights.impact
    span = highest - lowest
    final = (raw - lowest) / span if span > 0 else 0.0

    breakdown = ScoreBreakdown(
        relevance=round(relevance, 4),
        feasibility=round(feasibility.score, 4),
        expected_impact=round(impact, 4),
        effort_penalty=round(effort, 4),
        cost_penalty=round(cost, 4),
        weights=weights.as_dict(),
        final=round(max(0.0, min(1.0, final)), 4),
    )
    return breakdown, feasibility
