"""The structured project representation.

The central design rule, from README section 4.2: the application must
distinguish facts explicitly stated in the report from assumptions the AI
inferred. That is enforced here in the schema rather than left to prose, so an
unsupported "stated" claim is rejected before it can reach the user.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class ClaimSource(str, Enum):
    STATED = "stated"
    INFERRED = "inferred"


class Evidence(BaseModel):
    """A verbatim excerpt and the page it came from."""

    page: int = Field(ge=1)
    quote: str = Field(min_length=1, max_length=600)


class Claim(BaseModel):
    """One extracted fact, carrying its own provenance.

    A STATED claim must cite at least one piece of evidence. An INFERRED claim
    must not pretend to: it may carry evidence it reasoned from, but it is
    always labelled as inference in the UI and in the exported report.
    """

    value: str = Field(min_length=1)
    source: ClaimSource
    evidence: list[Evidence] = Field(default_factory=list)
    reasoning: str | None = Field(
        default=None,
        description="Why the AI inferred this. Required for INFERRED claims.",
    )

    @model_validator(mode="after")
    def _check_provenance(self) -> "Claim":
        if self.source is ClaimSource.STATED and not self.evidence:
            raise ValueError(
                "a 'stated' claim must cite at least one piece of evidence; "
                "use source='inferred' when the report does not say this"
            )
        return self

    @property
    def is_inferred(self) -> bool:
        return self.source is ClaimSource.INFERRED


class DatasetInfo(BaseModel):
    name: Claim | None = None
    size: Claim | None = None
    source: Claim | None = None
    preprocessing: list[Claim] = Field(default_factory=list)


class TechStack(BaseModel):
    languages: list[Claim] = Field(default_factory=list)
    frameworks: list[Claim] = Field(default_factory=list)
    libraries: list[Claim] = Field(default_factory=list)
    tools: list[Claim] = Field(default_factory=list)

    def all_items(self) -> list[Claim]:
        return [*self.languages, *self.frameworks, *self.libraries, *self.tools]


class EvaluationInfo(BaseModel):
    metrics: list[Claim] = Field(default_factory=list)
    reported_results: list[Claim] = Field(default_factory=list)
    validation_strategy: Claim | None = None


class ProjectProfile(BaseModel):
    """Everything the system believes about the uploaded project."""

    title: Claim
    domain: Claim
    problem_statement: Claim
    objectives: list[Claim] = Field(default_factory=list)
    intended_users: list[Claim] = Field(default_factory=list)
    methodology: list[Claim] = Field(default_factory=list)
    algorithms: list[Claim] = Field(default_factory=list)
    dataset: DatasetInfo = Field(default_factory=DatasetInfo)
    stack: TechStack = Field(default_factory=TechStack)
    evaluation: EvaluationInfo = Field(default_factory=EvaluationInfo)
    architecture_description: Claim | None = None
    stated_limitations: list[Claim] = Field(default_factory=list)
    extraction_notes: list[str] = Field(
        default_factory=list,
        description="What could not be determined, and any caveats about this profile.",
    )

    def all_claims(self) -> list[Claim]:
        claims: list[Claim] = [self.title, self.domain, self.problem_statement]
        claims += self.objectives + self.intended_users + self.methodology
        claims += self.algorithms + self.stated_limitations
        claims += self.stack.all_items()
        claims += self.dataset.preprocessing
        claims += self.evaluation.metrics + self.evaluation.reported_results
        for optional in (
            self.dataset.name,
            self.dataset.size,
            self.dataset.source,
            self.evaluation.validation_strategy,
            self.architecture_description,
        ):
            if optional is not None:
                claims.append(optional)
        return claims

    def counts_by_source(self) -> dict[str, int]:
        """Used by the UI to show how much of the profile is inference."""
        claims = self.all_claims()
        inferred = sum(1 for c in claims if c.is_inferred)
        return {
            "total": len(claims),
            "stated": len(claims) - inferred,
            "inferred": inferred,
        }
