"""Provider selection. The only place that knows which providers exist."""

from __future__ import annotations

from app.config import Settings
from app.errors import LLMUnavailable
from app.llm.base import LLMProvider
from app.llm.mock_provider import MockProvider


def get_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "mock":
        return MockProvider()

    if settings.llm_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise LLMUnavailable(
                "LLM_PROVIDER is set to 'anthropic' but ANTHROPIC_API_KEY is not "
                "set. Add the key, or set LLM_PROVIDER=mock to run without one."
            )
        from app.llm.anthropic_provider import AnthropicProvider

        return AnthropicProvider(
            api_key=settings.anthropic_api_key,
            model=settings.analysis_model,
            effort=settings.analysis_effort,
        )

    raise LLMUnavailable(f"Unknown LLM provider {settings.llm_provider!r}.")
