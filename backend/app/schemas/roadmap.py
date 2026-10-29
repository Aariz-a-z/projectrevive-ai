"""A phased plan for applying the recommendations.

The ordering is the substance here, and it is not arbitrary: work that makes
the project's measurements trustworthy comes first, because until evaluation
is sound there is no way to tell whether anything done afterwards helped. A
plan that opened with deployment would have you shipping a model whose
reported score might be an artefact of a single lucky split.

On time estimates, README section 4.7 says to label them as estimates rather
than guarantees. This goes further and gives none. How long any of this takes
depends on familiarity with the codebase, the state of the data and how much
of it is already half-done, none of which this system can see. A number
invented here would be exactly the kind of fabricated figure section 8
prohibits, and labelling it an estimate would not make it less invented.
Effort is reported as a complexity mix instead, which is derived from
something real.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.findings import FindingCategory
from app.schemas.recommendation import Complexity


class PhaseId(str, Enum):
    TRUSTWORTHY = "trustworthy"
    IMPROVE = "improve"
    REPRODUCIBLE = "reproducible"
    SHIP = "ship"


#: Which categories belong to which phase, and why that phase sits where it
#: does. Declared as data so the ordering can be read and argued with rather
#: than inferred from control flow.
PHASE_DEFINITIONS: dict[PhaseId, dict[str, object]] = {
    PhaseId.TRUSTWORTHY: {
        "title": "Make the results trustworthy",
        "rationale": (
            "Everything after this is measured against the evaluation set up "
            "here. Doing it later means every improvement in between was "
            "judged by a number that could not support the judgement."
        ),
        "categories": {
            FindingCategory.EVALUATION,
            FindingCategory.METRIC_SUITABILITY,
            FindingCategory.DATA_LEAKAGE,
            FindingCategory.BASELINE,
            FindingCategory.CLASS_IMBALANCE,
        },
    },
    PhaseId.IMPROVE: {
        "title": "Understand and improve the model",
        "rationale": (
            "With a measurement you can trust, changes here can be shown to "
            "help rather than assumed to. This is also where error analysis "
            "usually redirects the effort."
        ),
        "categories": {
            FindingCategory.FEATURE_ENGINEERING,
            FindingCategory.EXPLAINABILITY,
        },
    },
    PhaseId.REPRODUCIBLE: {
        "title": "Make it reproducible",
        "rationale": (
            "Once the results are worth keeping, they need to survive being "
            "re-run by someone else. Doing this before the work settles means "
            "pinning an environment you are still changing."
        ),
        "categories": {
            FindingCategory.REPRODUCIBILITY,
            FindingCategory.TESTING,
            FindingCategory.DEPENDENCIES,
        },
    },
    PhaseId.SHIP: {
        "title": "Ship it and watch it",
        "rationale": (
            "Last, because deploying a model whose evaluation you do not "
            "trust just puts an unreliable result in front of users faster."
        ),
        "categories": {
            FindingCategory.DEPLOYMENT,
            FindingCategory.SCALABILITY,
            FindingCategory.SECURITY,
        },
    },
}

PHASE_ORDER = list(PHASE_DEFINITIONS)


class Task(BaseModel):
    """One recommendation, expressed as work to do."""

    recommendation_id: str
    title: str
    why: str
    steps: list[str] = Field(min_length=1)
    deliverable: str
    validation: str
    complexity: Complexity
    dependencies: list[str] = Field(default_factory=list)
    addresses_findings: list[str] = Field(default_factory=list)


class Phase(BaseModel):
    id: PhaseId
    order: int = Field(ge=1)
    title: str
    rationale: str
    tasks: list[Task] = Field(default_factory=list)

    @property
    def complexity_mix(self) -> dict[str, int]:
        mix = {c.value: 0 for c in Complexity}
        for task in self.tasks:
            mix[task.complexity.value] += 1
        return mix


class Roadmap(BaseModel):
    phases: list[Phase] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @property
    def task_count(self) -> int:
        return sum(len(phase.tasks) for phase in self.phases)

    def complexity_mix(self) -> dict[str, int]:
        mix = {c.value: 0 for c in Complexity}
        for phase in self.phases:
            for key, value in phase.complexity_mix.items():
                mix[key] += value
        return mix
