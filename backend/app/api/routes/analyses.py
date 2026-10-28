"""Analysis endpoints: upload a report, read back the structured result."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.gaps import analyse_gaps
from app.analysis.profile import build_profile
from app.auth.deps import get_current_user
from app.config import Settings, get_settings
from app.db.models import Analysis, User
from app.db.session import get_db
from app.documents.extract import extract
from app.errors import AnalysisNotFound, EmptyDocument, FileTooLarge
from app.llm.registry import get_provider
from app.ratelimit.deps import limit_upload_for
from app.schemas.api import (
    AnalysisDetail,
    AnalysisProvenance,
    AnalysisSummary,
    UsageInfo,
)
from app.recommend.engine import recommend
from app.schemas.findings import FindingsReport
from app.schemas.project import ProjectProfile
from app.schemas.recommendation import RecommendationReport

router = APIRouter(prefix="/analyses", tags=["analyses"])

CHUNK = 256 * 1024


async def _read_limited(file: UploadFile, limit: int) -> bytes:
    """Read an upload, refusing to buffer more than `limit` bytes.

    Streaming the check means an oversized upload is rejected without first
    being held in memory in full.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise FileTooLarge()
        chunks.append(chunk)
    return b"".join(chunks)


def _provenance(row: Analysis) -> AnalysisProvenance:
    return AnalysisProvenance(
        provider=row.provider,
        model=row.model,
        is_mock=row.provider == "mock",
        usage=UsageInfo(
            input_tokens=row.input_tokens,
            output_tokens=row.output_tokens,
            cached_input_tokens=row.cached_input_tokens,
        ),
    )


def _to_detail(row: Analysis) -> AnalysisDetail:
    profile = ProjectProfile.model_validate(row.profile)
    findings = FindingsReport.model_validate(row.findings or {})
    recommendations = RecommendationReport.model_validate(row.recommendations or {})
    return AnalysisDetail(
        id=row.id,
        created_at=row.created_at,
        filename=row.filename,
        content_type=row.content_type,
        page_count=row.page_count,
        status=row.status,
        title=profile.title.value,
        provenance=_provenance(row),
        profile=profile,
        findings=findings,
        recommendations=recommendations,
        claim_counts=profile.counts_by_source(),
        finding_counts=findings.by_severity(),
        finding_sources=findings.counts_by_source(),
        warnings=list(row.warnings or []),
    )


@router.post("", response_model=AnalysisDetail, status_code=201)
async def create_analysis(
    file: UploadFile,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: User = Depends(get_current_user),
) -> AnalysisDetail:
    """Upload a project report and get its structured profile back.

    Processing is synchronous in this phase. The document bytes are never
    written to disk and are discarded once the profile is built.
    """
    # Checked before reading the body: an over-quota client should not get to
    # stream 20 MB first.
    limit_upload_for(user.id, settings)

    data = await _read_limited(file, settings.max_upload_bytes)
    if not data:
        raise EmptyDocument("No file content was received.")

    document = extract(data, file.filename or "upload", settings)
    provider = get_provider(settings)

    result = build_profile(document, provider)
    gaps = analyse_gaps(result.parsed, document, provider)
    advice = recommend(
        result.parsed,
        gaps.parsed.findings,
        document,
        embedder_name=settings.embedder,
    )

    row = Analysis(
        id=uuid.uuid4().hex,
        user_id=user.id,
        filename=document.filename,
        content_type=document.content_type,
        page_count=document.page_count,
        status="complete",
        provider=result.provider,
        model=result.model,
        # Both stages bill, so usage is the sum rather than the last call's.
        input_tokens=result.usage.input_tokens + gaps.usage.input_tokens,
        output_tokens=result.usage.output_tokens + gaps.usage.output_tokens,
        cached_input_tokens=(
            result.usage.cached_input_tokens + gaps.usage.cached_input_tokens
        ),
        profile=result.parsed.model_dump(mode="json"),
        findings=gaps.parsed.model_dump(mode="json"),
        recommendations=advice.model_dump(mode="json"),
        warnings=[*result.warnings, *gaps.warnings],
    )
    db.add(row)
    db.commit()

    return _to_detail(row)


@router.get("", response_model=list[AnalysisSummary])
def list_analyses(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AnalysisSummary]:
    rows = db.scalars(
        select(Analysis)
        .where(Analysis.user_id == user.id)
        .order_by(Analysis.created_at.desc())
        .limit(50)
    ).all()
    return [
        AnalysisSummary(
            id=row.id,
            created_at=row.created_at,
            filename=row.filename,
            page_count=row.page_count,
            status=row.status,
            title=(row.profile or {}).get("title", {}).get("value"),
            provenance=_provenance(row),
        )
        for row in rows
    ]


@router.get("/{analysis_id}", response_model=AnalysisDetail)
def get_analysis(
    analysis_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AnalysisDetail:
    row = db.get(Analysis, analysis_id)
    # Another account's analysis is reported as missing rather than forbidden,
    # so this endpoint cannot be used to discover which ids exist.
    if row is None or row.user_id != user.id:
        raise AnalysisNotFound()
    return _to_detail(row)


@router.delete("/{analysis_id}", status_code=204)
def delete_analysis(
    analysis_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    row = db.get(Analysis, analysis_id)
    if row is None or row.user_id != user.id:
        raise AnalysisNotFound()
    db.delete(row)
    db.commit()
