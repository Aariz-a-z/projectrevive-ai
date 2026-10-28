"""Anthropic implementation of the LLMProvider protocol.

Structured output, not prompt-and-hope. `messages.parse(output_format=Model)`
constrains the response to the schema and returns a validated Pydantic
instance, so there is no JSON scraping and no half-parsed profile reaching the
rest of the pipeline. Anything that does not validate raises here.

Three model-specific details that are easy to get wrong on the current models:

- Thinking cannot be disabled on Opus 5.5; `{"type": "disabled"}` and a token
  budget are both rejected. Depth is controlled with `output_config.effort`,
  whose default on this model is `medium` rather than `high`, so it is always
  set explicitly.
- Forced tool choice is rejected too, which is the other common way people
  coerce JSON out of a model. Structured outputs are the supported route.
- A policy decline arrives as HTTP 200 with `stop_reason == "refusal"`, not as
  an exception, so `stop_reason` is checked before the content is read.

Server-side fallbacks are enabled: on a decline the API re-runs the request on
a fallback model within the same call, and `response.model` reports whichever
model actually answered, which is what gets recorded as provenance.
"""

from __future__ import annotations

import logging

import anthropic
from pydantic import BaseModel, ValidationError

from app.errors import (
    LLMInvalidOutput,
    LLMOutputTruncated,
    LLMRefused,
    LLMUnavailable,
)
from app.llm.base import StructuredResult, Usage

logger = logging.getLogger(__name__)

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider:
    """Implements app.llm.base.LLMProvider."""

    name = "anthropic"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        effort: str = "high",
        max_tokens: int = 16000,
        timeout_seconds: float = 300.0,
    ) -> None:
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        self._client = anthropic.Anthropic(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=2,
        )

    def structured(
        self,
        *,
        system: str,
        document: str,
        schema: type[BaseModel],
        task: str = "",
    ) -> StructuredResult:
        try:
            response = self._client.beta.messages.parse(
                model=self.model,
                max_tokens=self.max_tokens,
                # Thinking is always on for the current Opus/Sonnet models;
                # "adaptive" is the explicit spelling of the default.
                thinking={"type": "adaptive"},
                output_config={"effort": self.effort},
                # Routes by refusal category, so no fallback model list has to
                # be maintained here.
                betas=[FALLBACK_BETA],
                fallbacks="default",
                # Caches the last cacheable block. The document dominates the
                # request, so a re-analysis of the same file is much cheaper.
                # Note this does not yet help across pipeline stages: a later
                # stage sends a different system prompt, and system is rendered
                # before messages, so the shared prefix ends there.
                cache_control={"type": "ephemeral"},
                system=system,
                messages=[{"role": "user", "content": document}],
                output_format=schema,
            )
        except anthropic.AuthenticationError as exc:
            raise LLMUnavailable(
                "The Anthropic API rejected the configured key. Check "
                "ANTHROPIC_API_KEY."
            ) from exc
        except anthropic.PermissionDeniedError as exc:
            raise LLMUnavailable(
                "The configured key is not permitted to use this model."
            ) from exc
        except anthropic.NotFoundError as exc:
            raise LLMUnavailable(
                f"The model {self.model!r} was not found. Check ANALYSIS_MODEL."
            ) from exc
        except anthropic.RateLimitError as exc:
            raise LLMUnavailable(
                "The analysis model is rate limited right now. Try again "
                "shortly."
            ) from exc
        except anthropic.BadRequestError as exc:
            # A 400 is our bug (bad parameters), not a transient fault, so it
            # is logged in full rather than quietly retried.
            logger.error("Anthropic rejected the request: %s", exc)
            raise LLMInvalidOutput(
                "The analysis request was rejected as malformed.",
                detail=str(exc)[:500],
            ) from exc
        except anthropic.APIStatusError as exc:
            logger.warning("Anthropic API error %s: %s", exc.status_code, exc)
            raise LLMUnavailable(
                f"The analysis model returned an error ({exc.status_code})."
            ) from exc
        except (anthropic.APITimeoutError, anthropic.APIConnectionError) as exc:
            raise LLMUnavailable(
                "Could not reach the analysis model before timing out."
            ) from exc
        except ValidationError as exc:
            # Output that did not match the schema. Rejected, never shown.
            logger.error("structured output failed schema validation: %s", exc)
            raise LLMInvalidOutput(detail=str(exc)[:500]) from exc

        return self._to_result(response, schema)

    def _to_result(self, response, schema: type[BaseModel]) -> StructuredResult:
        warnings: list[str] = []

        # A decline is a 200, so this must be checked before reading content.
        if response.stop_reason == "refusal":
            category = getattr(response.stop_details, "category", None)
            logger.warning("model declined the request (category=%s)", category)
            raise LLMRefused(
                detail=f"refusal category: {category}" if category else None
            )

        if response.stop_reason == "max_tokens":
            raise LLMOutputTruncated()

        parsed = getattr(response, "parsed_output", None)
        if parsed is None:
            raise LLMInvalidOutput(
                "The analysis model returned no structured output."
            )
        if not isinstance(parsed, schema):
            raise LLMInvalidOutput(
                f"Expected {schema.__name__} but the model returned "
                f"{type(parsed).__name__}."
            )

        # A fallback may have answered instead; record what actually ran.
        answered_by = getattr(response, "model", self.model) or self.model
        if answered_by != self.model:
            warnings.append(
                f"The request was declined by {self.model} and completed by "
                f"{answered_by} instead."
            )

        usage = response.usage
        return StructuredResult(
            parsed=parsed,
            provider=self.name,
            model=answered_by,
            usage=Usage(
                input_tokens=getattr(usage, "input_tokens", 0) or 0,
                output_tokens=getattr(usage, "output_tokens", 0) or 0,
                cached_input_tokens=getattr(usage, "cache_read_input_tokens", 0)
                or 0,
            ),
            warnings=warnings,
        )
