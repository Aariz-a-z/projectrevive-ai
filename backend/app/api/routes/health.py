"""Health and configuration reporting.

The config block is deliberately explicit about whether a real model is wired
up, so a demo is never mistaken for a real analysis and a missing key is
visible before an upload rather than after.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    return {
        "status": "ok",
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
