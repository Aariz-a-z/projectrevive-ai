"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.api.routes import analyses, health
from app.config import get_settings
from app.db.session import init_db
from app.errors import LLMInvalidOutput, ProjectReviveError

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="ProjectRevive AI",
        description=(
            "Analyses an existing AI/ML project report and recommends "
            "evidence-based improvements."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.exception_handler(ProjectReviveError)
    async def handle_domain_error(
        request: Request, exc: ProjectReviveError
    ) -> JSONResponse:
        if exc.status >= 500:
            logger.error("%s: %s", exc.code, exc.message, exc_info=exc)
        return JSONResponse(status_code=exc.status, content=exc.to_payload())

    @app.exception_handler(ValidationError)
    async def handle_model_validation(
        request: Request, exc: ValidationError
    ) -> JSONResponse:
        """A Pydantic failure here means our own data failed validation.

        Request-body validation is handled separately by FastAPI, so reaching
        this means structured model output (or a stored profile) did not match
        the schema. That is surfaced as a rejected analysis, not a crash.
        """
        logger.error("structured output failed validation: %s", exc)
        error = LLMInvalidOutput(detail=str(exc)[:1000])
        return JSONResponse(status_code=error.status, content=error.to_payload())

    app.include_router(health.router, prefix="/api")
    app.include_router(analyses.router, prefix="/api")

    return app


app = create_app()
