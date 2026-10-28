"""HTTP request and response shapes.

Kept separate from the domain schemas so the wire format can change without
touching the analysis pipeline, and so the frontend has one file to mirror.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.findings import FindingsReport
from app.schemas.project import ProjectProfile


class UsageInfo(BaseModel):
    """Measured token counts. Zero for the mock provider, which spends nothing."""

    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0


class AnalysisProvenance(BaseModel):
    """Who produced this analysis. Shown in the UI so results are never anonymous."""

    provider: str
    model: str
    is_mock: bool = Field(
        description="True when the analysis came from the deterministic mock "
        "provider rather than a language model."
    )
    usage: UsageInfo


class AnalysisSummary(BaseModel):
    id: str
    created_at: datetime
    filename: str
    page_count: int
    status: str
    title: str | None = None
    provenance: AnalysisProvenance


class AnalysisDetail(AnalysisSummary):
    content_type: str
    profile: ProjectProfile
    findings: FindingsReport
    claim_counts: dict[str, int]
    finding_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Findings by severity, for the dashboard summary.",
    )
    finding_sources: dict[str, int] = Field(
        default_factory=dict,
        description="How many findings came from rules versus the model.",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Caveats about this analysis: unverifiable citations, "
        "injection-looking content in the document, mock-provider notices.",
    )


class ErrorResponse(BaseModel):
    code: str
    message: str
    detail: str | None = None
