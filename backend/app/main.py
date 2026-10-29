"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.api.routes import analyses, health
from app.auth import routes as auth_routes
from app.auth.security import verify_signing_key
from app.config import get_settings
from app.db.migrate import ensure_schema
from app.db.session import engine
from app.errors import LLMInvalidOutput, ProjectReviveError

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Before anything can issue a session: a key too short to sign with is a
    # configuration error, not a warning to scroll past.
    verify_signing_key(get_settings())

    # Migrations, not create_all: the schema this process serves must be one
    # a migration produced, or the two diverge without anything noticing.
    ensure_schema(engine, get_settings())
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

    # allow_credentials is required for the session cookie to be sent on
    # cross-origin fetches from the frontend. It is only safe because
    # allow_origins names one exact origin -- with "*" the browser would
    # refuse, and widening it would expose authenticated endpoints.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )

    @app.exception_handler(ProjectReviveError)
    async def handle_domain_error(
        request: Request, exc: ProjectReviveError
    ) -> JSONResponse:
        if exc.status >= 500:
            logger.error("%s: %s", exc.code, exc.message, exc_info=exc)
        return JSONResponse(
            status_code=exc.status,
            content=exc.to_payload(),
            headers=exc.headers,
        )

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
    app.include_router(auth_routes.router, prefix="/api")
    app.include_router(analyses.router, prefix="/api")

    return app


app = create_app()
