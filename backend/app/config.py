"""Application settings. Every secret and tunable comes from the environment."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- LLM ---
    llm_provider: Literal["mock", "anthropic"] = "mock"
    anthropic_api_key: str | None = None
    analysis_model: str = "claude-opus-5-5"
    analysis_effort: Literal["low", "medium", "high", "xhigh", "max"] = "high"
    # 16k keeps a non-streaming request comfortably inside HTTP timeouts while
    # leaving room for a large structured profile.
    analysis_max_tokens: int = 16000
    analysis_timeout_seconds: float = 300.0

    # --- Recommendation engine ---
    embedder: Literal["tfidf", "sentence_transformer"] = "tfidf"

    # --- Storage ---
    database_url: str = "sqlite:///./projectrevive.db"
    # Bring the database to head on startup. Turn off where several instances
    # start at once (concurrent migrations race) or where schema changes must
    # be a deliberate deploy step; the app then refuses to start unless the
    # database is already at head.
    auto_migrate: bool = True

    # --- Auth ---
    # Leave SECRET_KEY unset in development: a random key is generated and
    # persisted to backend/.secret_key (gitignored) so sessions survive
    # reloads. It MUST be set explicitly in production.
    secret_key: str = ""
    access_token_minutes: int = 60 * 24 * 7
    cookie_name: str = "pr_session"
    cookie_secure: bool = False  # True behind HTTPS in production
    min_password_length: int = 10

    # --- Rate limiting ---
    # Limits are per process. With multiple workers each keeps its own
    # counters, so the effective limit multiplies by the worker count.
    rate_limit_enabled: bool = True
    login_attempts_per_ip: int = 20
    login_window_seconds: int = 300
    signup_attempts_per_ip: int = 5
    signup_window_seconds: int = 3600
    upload_per_user: int = 20
    upload_window_seconds: int = 3600
    # Consecutive failed sign-ins for one account before backoff begins.
    lockout_threshold: int = 5
    lockout_base_seconds: int = 30
    lockout_max_seconds: int = 600

    # Only enable behind a proxy that overwrites X-Forwarded-For. With no
    # such proxy, trusting the header lets any client forge its own address
    # and bypass every per-IP limit.
    #
    # This setting is only effective if the server also respects it. Uvicorn
    # enables proxy headers by default and rewrites the client address before
    # application code runs, so start the API with backend/run.py, which wires
    # uvicorn's option to this value.
    trust_proxy_headers: bool = False
    # Which peers may set forwarded headers, when they are trusted at all.
    forwarded_allow_ips: str = "127.0.0.1"

    # --- Upload limits (README section 10) ---
    max_upload_mb: int = 20
    # 300 until this was measured against a real deployment, where it was not
    # a limit at all: analysis runs synchronously inside the request, so the
    # page count decides how long one request occupies the only worker. On a
    # free Render instance 15 pages took 33 seconds and 20 pages killed the
    # service outright, taking the whole site down with it.
    #
    # 50 is what a capable host manages comfortably. It is deliberately a
    # setting rather than a constant, because the right value depends on the
    # instance: see MAX_PAGES in render.yaml, which lowers it for the free
    # tier. Raising it is safe only once analysis stops blocking the request.
    max_pages: int = 50
    extraction_timeout_seconds: int = 60

    # --- Optional features ---
    enable_ocr: bool = False

    # --- CORS ---
    frontend_origin: str = "http://localhost:3000"

    @field_validator("database_url")
    @classmethod
    def _normalise_database_url(cls, value: str) -> str:
        """Accept the `postgres://` form several providers hand out.

        SQLAlchemy 2 only recognises `postgresql://` and raises on
        `postgres://`, but Heroku, Railway and others still issue the shorter
        form. Rewriting it here means pasting the string a provider gives you
        works, instead of failing at startup with an error about a dialect
        that looks nothing like the problem.
        """
        if value.startswith("postgres://"):
            return "postgresql://" + value[len("postgres://") :]
        return value

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
