"""Analysis endpoints: upload a report, read back the structured result."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analysis.profile import build_profile
from app.config import Settings, get_settings
from app.db.models import Analysis
from app.db.session import get_db
from app.documents.extract import extract
from app.errors import AnalysisNotFound, EmptyDocument, FileTooLarge
from app.llm.registry import get_provider
from app.schemas.api import (
    AnalysisDetail,
    AnalysisProvenance,
    AnalysisSummary,
    UsageInfo,
)
from app.schemas.project import ProjectProfile

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
        claim_counts=profile.counts_by_source(),
        warnings=list(row.warnings or []),
    )


@router.post("", response_model=AnalysisDetail, status_code=201)
async def create_analysis(
    file: UploadFile,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AnalysisDetail:
    """Upload a project report and get its structured profile back.

    Processing is synchronous in this phase. The document bytes are never
    written to disk and are discarded once the profile is built.
    """
    data = await _read_limited(file, settings.max_upload_bytes)
    if not data:
        raise EmptyDocument("No file content was received.")

    document = extract(data, file.filename or "upload", settings)
    provider = get_provider(settings)
    result = build_profile(document, provider)

    row = Analysis(
        id=uuid.uuid4().hex,
        filename=document.filename,
        content_type=document.content_type,
        page_count=document.page_count,
        status="complete",
        provider=result.provider,
        model=result.model,
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
        cached_input_tokens=result.usage.cached_input_tokens,
        profile=result.parsed.model_dump(mode="json"),
        warnings=result.warnings,
    )
    db.add(row)
    db.commit()

    return _to_detail(row)


@router.get("", response_model=list[AnalysisSummary])
def list_analyses(db: Session = Depends(get_db)) -> list[AnalysisSummary]:
    rows = db.scalars(
        select(Analysis).order_by(Analysis.created_at.desc()).limit(50)
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
def get_analysis(analysis_id: str, db: Session = Depends(get_db)) -> AnalysisDetail:
    row = db.get(Analysis, analysis_id)
    if row is None:
        raise AnalysisNotFound()
    return _to_detail(row)
