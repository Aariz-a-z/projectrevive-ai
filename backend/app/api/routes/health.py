"""Health and configuration reporting.

The config block is deliberately explicit about whether a real model is wired
up, so a demo is never mistaken for a real analysis and a missing key is
visible before an upload rather than after.

The database is actually queried rather than assumed. A process that started
and then lost its database still accepts connections and still answers this
route, so a check that only proves the server is listening would report a
dead service as healthy -- which is exactly what the container healthcheck
would then believe.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


def _database_status(db: Session) -> tuple[bool, str]:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.error("health check: database unreachable: %s", exc)
        return False, "unreachable"
    return True, "ok"


@router.get("/health")
def health(
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    database_ok, database_state = _database_status(db)

    # 503 so a load balancer or container healthcheck takes this instance out
    # of rotation instead of sending it traffic it cannot serve.
    if not database_ok:
        response.status_code = 503

    return {
        "status": "ok" if database_ok else "degraded",
        "database": database_state,
        "llm": {
            "provider": settings.llm_provider,
            "model": (
                settings.analysis_model
                if settings.llm_provider == "anthropic"
                else "mock-deterministic-v1"
            ),
            "api_key_configured": bool(settings.anthropic_api_key),
            "is_mock": settings.llm_provider == "mock",
        },
        "embedder": settings.embedder,
        "limits": {
            "max_upload_mb": settings.max_upload_mb,
            "max_pages": settings.max_pages,
        },
        "ocr_enabled": settings.enable_ocr,
    }
