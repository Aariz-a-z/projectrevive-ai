"""The evaluation set format.

A case describes a project and the findings a reviewer would expect for it,
then grades knowledge base entries by how appropriate they are. Cases specify
the profile and findings directly rather than supplying a report to extract,
so what is being measured is the recommender alone. Extraction quality is a
separate concern and mixing the two would make a regression in either look
like a regression in the other.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.schemas.findings import (
    DetectedBy,
    Finding,
    FindingCategory,
    FindingKind,
    Severity,
)
from app.schemas.project import Claim, ClaimSource, DatasetInfo, EvaluationInfo
from app.schemas.project import ProjectProfile, TechStack

MAX_GRADE = 3


class CaseFinding(BaseModel):
    """A finding a reviewer would expect this project to produce."""

    rule_id: str | None = None
    category: FindingCategory
    severity: Severity = Severity.MEDIUM
    title: str = "expected finding"

    def to_finding(self) -> Finding:
        return Finding(
            title=self.title,
            category=self.category,
            kind=FindingKind.GAP,
            severity=self.severity,
            explanation=(
                "Supplied by the evaluation set to stand in for a detected "
                "finding."
            ),
            searched_for="evaluation fixture",
            detected_by=DetectedBy.RULE if self.rule_id else DetectedBy.MODEL,
            rule_id=self.rule_id,
        )


class CaseProject(BaseModel):
    title: str
    domain: str
    problem: str
    algorithms: list[str] = Field(default_factory=list)
    libraries: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    def to_profile(self) -> ProjectProfile:
        def inferred(value: str) -> Claim:
            return Claim(
                value=value,
                source=ClaimSource.INFERRED,
                reasoning="Supplied directly by the evaluation set.",
            )

        return ProjectProfile(
            title=inferred(self.title),
            domain=inferred(self.domain),
            problem_statement=inferred(self.problem),
            algorithms=[inferred(a) for a in self.algorithms],
            stack=TechStack(
                libraries=[inferred(x) for x in self.libraries],
                frameworks=[inferred(x) for x in self.frameworks],
            ),
            dataset=DatasetInfo(),
            evaluation=EvaluationInfo(metrics=[inferred(m) for m in self.metrics]),
            stated_limitations=[inferred(x) for x in self.limitations],
        )


class EvalCase(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,60}$")
    title: str
    rationale: str = Field(
        min_length=20,
        description="Why these grades were assigned. Makes a label arguable.",
    )
    project: CaseProject
    findings: list[CaseFinding] = Field(default_factory=list)
    judgments: dict[str, int] = Field(
        description="Knowledge base entry id -> relevance grade 0-3."
    )

    @field_validator("judgments")
    @classmethod
    def _grades_in_range(cls, value: dict[str, int]) -> dict[str, int]:
        for entry_id, grade in value.items():
            if not 0 <= grade <= MAX_GRADE:
                raise ValueError(
                    f"grade for {entry_id!r} is {grade}, must be 0-{MAX_GRADE}"
                )
        return value
