"""Comparing the project's current stack with what the analysis proposes.

README section 4.5 requires something most "modernise your stack" tools get
wrong: the system must be able to recommend **keeping** a technology that is
already appropriate. A comparison that only ever suggests replacements is not
an analysis, it is a sales pitch.

So KEEP is a first-class verdict with its own reasoning, not the absence of a
recommendation. And nothing is marked for replacement merely because something
newer exists — section 4.3 forbids that, and it is enforced here by there
being no code path that can produce a REPLACE verdict from age alone. A
replacement has to be proposed by a knowledge base entry that says what it
replaces and why.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from app.schemas.project import Evidence
from app.schemas.recommendation import Complexity, CostBand


class StackVerdict(str, Enum):
    KEEP = "keep"
    ADD = "add"
    REPLACE = "replace"


class StackEntry(BaseModel):
    name: str
    category: str = Field(description="language, framework, library or tool")
    verdict: StackVerdict
    rationale: str = Field(min_length=10)

    #: Where the report mentions this. Empty for anything being proposed,
    #: which by definition is not in the report.
    evidence: list[Evidence] = Field(default_factory=list)

    #: Recommendation ids that introduce or replace this.
    introduced_by: list[str] = Field(default_factory=list)
    replaces: str | None = None

    migration_complexity: Complexity | None = None
    cost: CostBand | None = None

    @model_validator(mode="after")
    def _check_support(self) -> "StackEntry":
        if self.verdict is StackVerdict.KEEP and not self.evidence:
            raise ValueError(
                "a 'keep' verdict is about something the report uses, so it "
                "must cite where the report mentions it"
            )
        if self.verdict is not StackVerdict.KEEP and not self.introduced_by:
            raise ValueError(
                f"a '{self.verdict.value}' verdict must name the "
                "recommendation that proposes it; nothing should appear in "
                "the proposed stack without a reason attached"
            )
        if self.verdict is StackVerdict.REPLACE and not self.replaces:
            raise ValueError("a 'replace' verdict must say what it replaces")
        return self


class StackComparison(BaseModel):
    entries: list[StackEntry] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    def by_verdict(self) -> dict[str, int]:
        counts = {v.value: 0 for v in StackVerdict}
        for entry in self.entries:
            counts[entry.verdict.value] += 1
        return counts

    def of(self, verdict: StackVerdict) -> list[StackEntry]:
        return [e for e in self.entries if e.verdict is verdict]
