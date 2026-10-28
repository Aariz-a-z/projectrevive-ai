"""The Anthropic provider, exercised against a stubbed SDK client.

No test here reaches the network or spends money. The SDK call is replaced
with a stub, which lets the failure paths that matter most -- a policy
decline, a truncated response, schema drift, and every error class -- be
tested deterministically. Those are precisely the paths that are hard to
trigger against the live API and so tend to go unverified until production.
"""

from __future__ import annotations

from types import SimpleNamespace

import anthropic
import pytest
from pydantic import BaseModel, ValidationError

from app.errors import (
    LLMInvalidOutput,
    LLMOutputTruncated,
    LLMRefused,
    LLMUnavailable,
)
from app.llm.anthropic_provider import FALLBACK_BETA, AnthropicProvider


class Tiny(BaseModel):
    answer: str


def _response(
    *,
    parsed=None,
    stop_reason: str = "end_turn",
    model: str = "claude-opus-5-5",
    stop_details=None,
    input_tokens: int = 1000,
    output_tokens: int = 200,
    cache_read: int = 0,
):
    return SimpleNamespace(
        parsed_output=Tiny(answer="ok") if parsed is None else parsed,
        stop_reason=stop_reason,
        stop_details=stop_details,
        model=model,
        usage=SimpleNamespace(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_input_tokens=cache_read,
        ),
    )


def _provider(monkeypatch, result) -> tuple[AnthropicProvider, dict]:
    """Build a provider whose SDK call returns `result` (or raises it)."""
    captured: dict = {}

    def fake_parse(**kwargs):
        captured.update(kwargs)
        if isinstance(result, BaseException):
            raise result
        return result

    provider = AnthropicProvider(api_key="sk-test", model="claude-opus-5-5")
    monkeypatch.setattr(
        provider._client.beta.messages, "parse", fake_parse, raising=True
    )
    return provider, captured


def _call(provider: AnthropicProvider):
    return provider.structured(
        system="You analyse documents.", document="some text", schema=Tiny
    )


class TestRequestShape:
    """The parameters are the contract with the model; assert them directly."""

    def test_sends_the_documented_parameters(self, monkeypatch) -> None:
        provider, sent = _provider(monkeypatch, _response())
        _call(provider)

        assert sent["model"] == "claude-opus-5-5"
        assert sent["output_format"] is Tiny
        assert sent["output_config"] == {"effort": "high"}
        assert sent["thinking"] == {"type": "adaptive"}
        assert sent["max_tokens"] == 16000

    def test_enables_server_side_fallbacks(self, monkeypatch) -> None:
        provider, sent = _provider(monkeypatch, _response())
        _call(provider)

        assert FALLBACK_BETA in sent["betas"]
        assert sent["fallbacks"] == "default"

    def test_enables_prompt_caching(self, monkeypatch) -> None:
        provider, sent = _provider(monkeypatch, _response())
        _call(provider)
        assert sent["cache_control"] == {"type": "ephemeral"}

    def test_document_goes_in_a_user_message_not_the_system_prompt(
        self, monkeypatch
    ) -> None:
        """Untrusted document text must never gain system-prompt authority."""
        provider, sent = _provider(monkeypatch, _response())
        provider.structured(
            system="SYSTEM RULES", document="UNTRUSTED DOC", schema=Tiny
        )

        assert "UNTRUSTED DOC" not in str(sent["system"])
        assert sent["messages"] == [{"role": "user", "content": "UNTRUSTED DOC"}]

    def test_effort_is_configurable(self, monkeypatch) -> None:
        provider, sent = _provider(monkeypatch, _response())
        provider.effort = "low"
        _call(provider)
        assert sent["output_config"] == {"effort": "low"}


class TestSuccess:
    def test_returns_the_validated_model(self, monkeypatch) -> None:
        provider, _ = _provider(
            monkeypatch, _response(parsed=Tiny(answer="forty-two"))
        )
        result = _call(provider)

        assert isinstance(result.parsed, Tiny)
        assert result.parsed.answer == "forty-two"
        assert result.provider == "anthropic"

    def test_reports_measured_token_usage(self, monkeypatch) -> None:
        provider, _ = _provider(
            monkeypatch,
            _response(input_tokens=12_345, output_tokens=678, cache_read=9_000),
        )
        result = _call(provider)

        assert result.usage.input_tokens == 12_345
        assert result.usage.output_tokens == 678
        assert result.usage.cached_input_tokens == 9_000

    def test_records_the_model_that_actually_answered(self, monkeypatch) -> None:
        """A fallback means provenance must not claim the requested model."""
        provider, _ = _provider(
            monkeypatch, _response(model="claude-opus-4-8")
        )
        result = _call(provider)

        assert result.model == "claude-opus-4-8"
        assert any("claude-opus-4-8" in w for w in result.warnings)

    def test_no_warning_when_the_requested_model_answered(
        self, monkeypatch
    ) -> None:
        provider, _ = _provider(monkeypatch, _response(model="claude-opus-5-5"))
        assert _call(provider).warnings == []


class TestStopReasons:
    def test_a_refusal_is_surfaced_not_treated_as_success(
        self, monkeypatch
    ) -> None:
        """A decline arrives as HTTP 200, so it must be checked explicitly."""
        provider, _ = _provider(
            monkeypatch,
            _response(
                stop_reason="refusal",
                stop_details=SimpleNamespace(category="cyber"),
            ),
        )
        with pytest.raises(LLMRefused) as exc:
            _call(provider)
        assert "cyber" in (exc.value.detail or "")

    def test_truncated_output_is_rejected(self, monkeypatch) -> None:
        provider, _ = _provider(monkeypatch, _response(stop_reason="max_tokens"))
        with pytest.raises(LLMOutputTruncated):
            _call(provider)

    def test_missing_structured_output_is_rejected(self, monkeypatch) -> None:
        provider, _ = _provider(monkeypatch, _response(parsed=False))
        # parsed=False -> parsed_output is False, which is not a Tiny
        with pytest.raises(LLMInvalidOutput):
            _call(provider)

    def test_wrong_schema_type_is_rejected(self, monkeypatch) -> None:
        class Other(BaseModel):
            other: int

        provider, _ = _provider(monkeypatch, _response(parsed=Other(other=1)))
        with pytest.raises(LLMInvalidOutput):
            _call(provider)


def _api_error(error_cls, status: int, message: str):
    """Build a real SDK exception.

    The SDK's constructors read `response.request`, so these are genuine
    httpx2 objects rather than stand-ins -- which also means the test keeps
    working if the SDK changes what it reads from them.
    """
    import httpx2

    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx2.Response(status, request=request)
    return error_cls(message, response=response, body=None)


class TestErrorMapping:
    """Each SDK error becomes a specific, actionable message."""

    def _raise(self, monkeypatch, exc):
        provider, _ = _provider(monkeypatch, exc)
        return provider

    def test_bad_key(self, monkeypatch) -> None:
        err = _api_error(anthropic.AuthenticationError, 401, "bad key")
        with pytest.raises(LLMUnavailable, match="ANTHROPIC_API_KEY"):
            _call(self._raise(monkeypatch, err))

    def test_unknown_model(self, monkeypatch) -> None:
        err = _api_error(anthropic.NotFoundError, 404, "no model")
        with pytest.raises(LLMUnavailable, match="ANALYSIS_MODEL"):
            _call(self._raise(monkeypatch, err))

    def test_rate_limited(self, monkeypatch) -> None:
        err = _api_error(anthropic.RateLimitError, 429, "slow down")
        with pytest.raises(LLMUnavailable, match="rate limited"):
            _call(self._raise(monkeypatch, err))

    def test_server_error(self, monkeypatch) -> None:
        err = _api_error(anthropic.InternalServerError, 500, "boom")
        with pytest.raises(LLMUnavailable, match="returned an error"):
            _call(self._raise(monkeypatch, err))

    def test_bad_request_is_reported_as_our_bug(self, monkeypatch) -> None:
        """A 400 means we sent bad parameters; it must not look transient."""
        err = _api_error(anthropic.BadRequestError, 400, "bad parameter")
        with pytest.raises(LLMInvalidOutput):
            _call(self._raise(monkeypatch, err))

    def test_timeout(self, monkeypatch) -> None:
        err = anthropic.APITimeoutError(request=SimpleNamespace())
        with pytest.raises(LLMUnavailable, match="timing out"):
            _call(self._raise(monkeypatch, err))

    def test_schema_validation_failure_is_not_a_crash(self, monkeypatch) -> None:
        try:
            Tiny(answer=None)  # type: ignore[arg-type]
        except ValidationError as real_error:
            with pytest.raises(LLMInvalidOutput):
                _call(self._raise(monkeypatch, real_error))


class TestRegistry:
    def test_registry_builds_the_provider_when_a_key_is_present(self) -> None:
        from app.config import Settings
        from app.llm.registry import get_provider

        provider = get_provider(
            Settings(
                llm_provider="anthropic",
                anthropic_api_key="sk-test",
                analysis_model="claude-opus-5-5",
            )
        )
        assert isinstance(provider, AnthropicProvider)
        assert provider.model == "claude-opus-5-5"
