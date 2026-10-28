"""Recommendations and the scores that order them.

The score here is an **explicitly configurable weighted sum**, not a measured
quantity. README section 4.4 is direct about this: arbitrary scores must not be
presented as scientifically validated measurements. So `ScoreBreakdown` carries
every component and every weight that produced the final number, the API
returns it, and the UI shows it. A reader who disagrees with the weighting can
see exactly what it was rather than guessing why one item outranked another.

Two of the components are genuinely different in kind, and the schema keeps
them apart:

- `relevance` and `feasibility` are computed from this project -- similarity to
  the project's own text, and whether its constraints allow the change.
- `expected_impact` is a judgement entered by whoever wrote the knowledge base
  entry. It is the same number for every project that matches that entry, and
  is labelled an estimate wherever it is shown.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from app.schemas.project import Evidence


class Complexity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CostBand(str, Enum):
    """Money and compute together, as bands rather than invented figures."""

    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SkillLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class MatchedBy(str, Enum):
    """How this recommendation reached the shortlist.

    KNOWLEDGE means a rule-detected finding named it directly, which is the
    strongest link. CONTENT means it was matched by similarity to the project
    description, which is weaker and is labelled as such.
    """

    KNOWLEDGE = "knowledge"
    CONTENT = "content"
    BOTH = "both"


COMPLEXITY_EFFORT = {Complexity.LOW: 0.2, Complexity.MEDIUM: 0.55, Complexity.HIGH: 1.0}
COST_PENALTY = {
    CostBand.NONE: 0.0,
    CostBand.LOW: 0.25,
    CostBand.MEDIUM: 0.6,
    CostBand.HIGH: 1.0,
}


class Weights(BaseModel):
    """The configurable part of the formula from README section 7.

    Defaults are a starting point chosen by hand, not a tuned result. Section 8
    calls for them to be refined through evaluation; until that has happened
    they are exactly what they look like.
    """

    relevance: float = 0.40
    feasibility: float = 0.20
    impact: float = 0.25
    effort: float = 0.10
    cost: float = 0.05

    def as_dict(self) -> dict[str, float]:
        return self.model_dump()


class ScoreBreakdown(BaseModel):
    relevance: float = Field(ge=0.0, le=1.0)
    feasibility: float = Field(ge=0.0, le=1.0)
    expected_impact: float = Field(ge=0.0, le=1.0)
    effort_penalty: float = Field(ge=0.0, le=1.0)
    cost_penalty: float = Field(ge=0.0, le=1.0)
    weights: dict[str, float]
    final: float

    @property
    def formula(self) -> str:
        w = self.weights
        # ASCII only: this string is printed to consoles and logs whose
        # encoding is not guaranteed to be UTF-8.
        return (
            f"{w['relevance']}*relevance + {w['feasibility']}*feasibility + "
            f"{w['impact']}*impact - {w['effort']}*effort - {w['cost']}*cost"
        )


class Recommendation(BaseModel):
    """Every field README section 4.4 asks a recommendation to carry."""

    id: str
    title: str

    problem_addressed: str
    current_approach: str
    proposed_approach: str
    reason: str

    # Carried through from the finding that triggered this, so a
    # recommendation can be traced back to a page of the user's own report.
    evidence: list[Evidence] = Field(default_factory=list)
    addresses_findings: list[str] = Field(default_factory=list)

    expected_benefits: list[str] = Field(default_factory=list)
    trade_offs: list[str] = Field(default_factory=list)

    complexity: Complexity
    cost: CostBand
    skill_level: SkillLevel
    dependencies: list[str] = Field(default_factory=list)
    implementation_steps: list[str] = Field(default_factory=list)
    validation_method: str

    matched_by: MatchedBy
    score: ScoreBreakdown
    constraint_notes: list[str] = Field(
        default_factory=list,
        description="Why feasibility was reduced, if it was.",
    )

    @model_validator(mode="after")
    def _trade_offs_are_required(self) -> "Recommendation":
        """A recommendation with no stated downside is advertising.

        Section 4.4 requires drawbacks and trade-offs on every recommendation,
        and a knowledge base entry that forgets them should fail loudly rather
        than quietly present a change as free.
        """
        if not self.trade_offs:
            raise ValueError(
                f"recommendation {self.id!r} states no trade-offs; every "
                "change has a cost and it must be named"
            )
        return self


class UserConstraints(BaseModel):
    """What the user can actually do.

    Nothing here is collected from the user yet, so every field is either a
    default or inferred from the report. `assumptions` records which, because a
    feasibility score computed from a guess must not look like one computed
    from fact.
    """

    has_gpu: bool = False
    dataset_rows: int | None = None
    skill_level: SkillLevel = SkillLevel.INTERMEDIATE
    budget: CostBand = CostBand.LOW
    needs_deployment: bool = True
    assumptions: list[str] = Field(default_factory=list)


class RecommendationReport(BaseModel):
    recommendations: list[Recommendation] = Field(default_factory=list)
    weights: Weights = Field(default_factory=Weights)
    constraints: UserConstraints = Field(default_factory=UserConstraints)
    notes: list[str] = Field(default_factory=list)
    excluded: list[str] = Field(
        default_factory=list,
        description="Entries ruled out by a hard constraint, and why.",
    )

    def counts_by_match(self) -> dict[str, int]:
        counts = {m.value: 0 for m in MatchedBy}
        for item in self.recommendations:
            counts[item.matched_by.value] += 1
        return counts
