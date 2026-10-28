"""Weaknesses and gaps found in a project.

The provenance rule from `project.py` continues here, adapted to the fact that
a finding can be about something *present* or something *absent*:

- A WEAKNESS says something in the report is problematic, so it must quote the
  report. No quote, no weakness.
- A GAP says something expected is missing. An absence cannot be quoted, so a
  gap instead has to state what was looked for, which is the only way a reader
  can check whether the search was reasonable.

`detected_by` is kept on every finding because the two sources have genuinely
different trustworthiness. A rule fired on structured data and can be read in
`app/analysis/rules.py`; a model finding is a judgement that may be wrong. The
UI shows the difference rather than averaging it away.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from app.schemas.project import Evidence


class FindingCategory(str, Enum):
    """Taken from README section 4.3, plus reproducibility."""

    EVALUATION = "evaluation"
    DATA_LEAKAGE = "data_leakage"
    CLASS_IMBALANCE = "class_imbalance"
    METRIC_SUITABILITY = "metric_suitability"
    FEATURE_ENGINEERING = "feature_engineering"
    EXPLAINABILITY = "explainability"
    SCALABILITY = "scalability"
    SECURITY = "security"
    DEPENDENCIES = "dependencies"
    DEPLOYMENT = "deployment"
    TESTING = "testing"
    REPRODUCIBILITY = "reproducibility"
    BASELINE = "baseline"


class FindingKind(str, Enum):
    WEAKNESS = "weakness"
    GAP = "gap"


class Severity(str, Enum):
    """How much this undermines the project's own conclusions.

    Deliberately about validity, not effort. HIGH means the reported results
    may not mean what the report says they mean.
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DetectedBy(str, Enum):
    RULE = "rule"
    MODEL = "model"


SEVERITY_ORDER = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}


class Finding(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    category: FindingCategory
    kind: FindingKind
    severity: Severity
    explanation: str = Field(
        min_length=20,
        description=(
            "Why this matters for THIS project. Not a definition of the "
            "general concept."
        ),
    )
    evidence: list[Evidence] = Field(default_factory=list)
    searched_for: str | None = Field(
        default=None,
        description="For a gap: what was looked for and not found.",
    )
    detected_by: DetectedBy
    rule_id: str | None = None

    @model_validator(mode="after")
    def _check_support(self) -> "Finding":
        if self.kind is FindingKind.WEAKNESS and not self.evidence:
            raise ValueError(
                "a 'weakness' must quote the report text it objects to; "
                "use kind='gap' when the problem is that something is absent"
            )
        if self.kind is FindingKind.GAP and not (self.searched_for or "").strip():
            raise ValueError(
                "a 'gap' must say what was looked for, since an absence "
                "cannot be quoted"
            )
        if self.detected_by is DetectedBy.RULE and not self.rule_id:
            raise ValueError("a rule-detected finding must name its rule_id")
        return self

    @property
    def sort_key(self) -> tuple[int, int, str]:
        # Rules before model findings at equal severity: they are checkable.
        return (
            SEVERITY_ORDER[self.severity],
            0 if self.detected_by is DetectedBy.RULE else 1,
            self.title.lower(),
        )


class GapAnalysis(BaseModel):
    """The model-generated half of the analysis.

    Kept as its own schema so the model is asked for exactly this and nothing
    else, and so its output can be validated before being merged with the
    deterministic findings.
    """

    findings: list[Finding] = Field(default_factory=list)
    notes: list[str] = Field(
        default_factory=list,
        description="What could not be assessed from the document.",
    )


class FindingsReport(BaseModel):
    """What the API returns: merged, verified, ordered."""

    findings: list[Finding] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    def by_severity(self) -> dict[str, int]:
        counts = {s.value: 0 for s in Severity}
        for finding in self.findings:
            counts[finding.severity.value] += 1
        return counts

    def counts_by_source(self) -> dict[str, int]:
        rules = sum(
            1 for f in self.findings if f.detected_by is DetectedBy.RULE
        )
        return {
            "total": len(self.findings),
            "rule": rules,
            "model": len(self.findings) - rules,
        }
