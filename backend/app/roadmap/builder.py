"""Turning ranked recommendations into a phased plan.

Every task comes from a recommendation, so nothing appears in the plan that
was not justified earlier. Within a phase the existing ranking is preserved:
it already accounts for relevance, feasibility, impact, effort and cost, and
re-sorting here would quietly apply a second, undocumented set of priorities.
"""

from __future__ import annotations

from app.knowledge.loader import load_knowledge_base
from app.schemas.findings import FindingCategory
from app.schemas.recommendation import Recommendation
from app.schemas.roadmap import (
    PHASE_DEFINITIONS,
    PHASE_ORDER,
    Phase,
    PhaseId,
    Roadmap,
    Task,
)

#: Anything whose category is not claimed by a phase lands here. Better than
#: dropping the task, which would make the plan quietly incomplete.
FALLBACK_PHASE = PhaseId.IMPROVE


def _phase_for(category: FindingCategory) -> PhaseId:
    for phase_id, definition in PHASE_DEFINITIONS.items():
        if category in definition["categories"]:  # type: ignore[operator]
            return phase_id
    return FALLBACK_PHASE


def _task(recommendation: Recommendation) -> Task:
    return Task(
        recommendation_id=recommendation.id,
        title=recommendation.title,
        why=recommendation.reason,
        steps=recommendation.implementation_steps,
        deliverable=recommendation.proposed_approach,
        validation=recommendation.validation_method,
        complexity=recommendation.complexity,
        dependencies=recommendation.dependencies,
        addresses_findings=recommendation.addresses_findings,
    )


def build_roadmap(recommendations: list[Recommendation]) -> Roadmap:
    """Group the recommendations into ordered phases."""
    by_id = {entry.id: entry for entry in load_knowledge_base()}
    buckets: dict[PhaseId, list[Task]] = {phase: [] for phase in PHASE_ORDER}

    for recommendation in recommendations:
        entry = by_id.get(recommendation.id)
        category = entry.category if entry else FindingCategory.EVALUATION
        buckets[_phase_for(category)].append(_task(recommendation))

    phases = [
        Phase(
            id=phase_id,
            order=index + 1,
            title=str(PHASE_DEFINITIONS[phase_id]["title"]),
            rationale=str(PHASE_DEFINITIONS[phase_id]["rationale"]),
            tasks=buckets[phase_id],
        )
        for index, phase_id in enumerate(PHASE_ORDER)
        # An empty phase is noise; the project already does that part well
        # enough that nothing was recommended for it.
        if buckets[phase_id]
    ]

    notes = [
        "Phases are ordered so that work the later phases are measured "
        "against happens first. Within a phase, tasks keep the ranking from "
        "the recommendations.",
        "No time estimates are given. How long this takes depends on "
        "familiarity with the code, the state of the data and how much is "
        "already half-done, none of which this analysis can see. Effort is "
        "shown as a complexity mix instead.",
    ]
    if not recommendations:
        notes.append("No recommendations were produced, so there is no plan.")

    return Roadmap(phases=phases, notes=notes)
