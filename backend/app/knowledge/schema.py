"""The curated knowledge base of candidate improvements.

README section 5 requires this to be inspectable and editable, so it lives as
YAML under `kb/` rather than in code or a database. Anyone can read an entry,
disagree with its `impact` estimate, and change it in a pull request.

What this is not: learned. There is no interaction data, nothing was trained,
and nothing here was derived from user behaviour. Every field was written by
hand, and `impact` in particular is a considered guess. The UI says so.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.schemas.findings import FindingCategory
from app.schemas.recommendation import Complexity, CostBand, SkillLevel


class KBEntry(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,60}$")
    title: str = Field(min_length=5, max_length=120)
    category: FindingCategory

    # --- how this entry is matched ------------------------------------------
    addresses_rules: list[str] = Field(
        default_factory=list,
        description="Rule ids from app/analysis/rules.py this directly fixes.",
    )
    addresses_categories: list[FindingCategory] = Field(default_factory=list)
    domains: list[str] = Field(
        default_factory=list,
        description="Project domains this suits. Empty means any domain.",
    )
    keywords: list[str] = Field(
        default_factory=list,
        description="Extra text used for content-based similarity.",
    )

    # --- the recommendation content -----------------------------------------
    problem: str = Field(min_length=20)
    current_approach: str = Field(min_length=10)
    proposed_approach: str = Field(min_length=20)
    reason: str = Field(min_length=20)
    expected_benefits: list[str] = Field(min_length=1)
    trade_offs: list[str] = Field(min_length=1)
    implementation_steps: list[str] = Field(min_length=1)
    validation_method: str = Field(min_length=10)
    dependencies: list[str] = Field(default_factory=list)

    # --- ranking inputs and constraints -------------------------------------
    complexity: Complexity
    cost: CostBand
    skill_level: SkillLevel = SkillLevel.INTERMEDIATE
    impact: float = Field(
        ge=0.0,
        le=1.0,
        description="Hand-assigned expected benefit. An estimate, not a measurement.",
    )
    requires_gpu: bool = False
    min_dataset_rows: int | None = None

    @field_validator("trade_offs")
    @classmethod
    def _no_empty_tradeoffs(cls, value: list[str]) -> list[str]:
        """Reject a trade-off list that exists but says nothing."""
        cleaned = [t for t in value if t.strip()]
        if not cleaned:
            raise ValueError("every entry must state at least one real trade-off")
        return cleaned

    def match_text(self) -> str:
        """The text used for content-based similarity against a project."""
        return " ".join(
            [
                self.title,
                self.problem,
                self.proposed_approach,
                " ".join(self.keywords),
                " ".join(self.domains),
                self.category.value.replace("_", " "),
            ]
        )
