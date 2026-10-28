"""Application settings. Every secret and tunable comes from the environment."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- LLM ---
    llm_provider: Literal["mock", "anthropic"] = "mock"
    anthropic_api_key: str | None = None
    analysis_model: str = "claude-opus-5-5"
    analysis_effort: Literal["low", "medium", "high", "xhigh", "max"] = "high"

    # --- Recommendation engine ---
    embedder: Literal["tfidf", "sentence_transformer"] = "tfidf"

    # --- Storage ---
    database_url: str = "sqlite:///./projectrevive.db"

    # --- Upload limits (README section 10) ---
    max_upload_mb: int = 20
    max_pages: int = 300
    extraction_timeout_seconds: int = 60

    # --- Optional features ---
    enable_ocr: bool = False

    # --- CORS ---
    frontend_origin: str = "http://localhost:3000"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
