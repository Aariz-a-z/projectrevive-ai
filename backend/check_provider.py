"""Verify a real Anthropic API key end to end, cheaply.

The provider's own tests run against a stub, so they prove the request shape
and every failure path but never touch the network. This script is the other
half: one small real call that proves the key works, the model exists, and
structured output comes back validated.

    cd backend
    ./.venv/Scripts/python.exe check_provider.py       # Windows
    python check_provider.py                           # macOS/Linux

It costs a fraction of a cent. Nothing is written to the database.
"""

from __future__ import annotations

import sys

from pydantic import BaseModel, Field

from app.config import get_settings
from app.errors import ProjectReviveError
from app.llm.anthropic_provider import AnthropicProvider

# Per-million-token prices, for the estimate printed below. Update if pricing
# changes; this is a convenience, not a billing source of truth.
PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}


class SmokeTest(BaseModel):
    """Deliberately tiny, so the check costs almost nothing."""

    language: str = Field(description="The language the sample text is written in.")
    word_count: int = Field(description="How many words the sample contains.")
    is_about_machine_learning: bool


SAMPLE = "The model was trained on MNIST using a convolutional neural network."


def main() -> int:
    settings = get_settings()

    if not settings.anthropic_api_key:
        print("ANTHROPIC_API_KEY is not set.")
        print("Add it to backend/.env, then run this again.")
        return 1

    print(f"model   : {settings.analysis_model}")
    print(f"effort  : {settings.analysis_effort}")
    print("calling : api.anthropic.com ...\n")

    provider = AnthropicProvider(
        api_key=settings.anthropic_api_key,
        model=settings.analysis_model,
        effort=settings.analysis_effort,
        max_tokens=settings.analysis_max_tokens,
        timeout_seconds=settings.analysis_timeout_seconds,
    )

    try:
        result = provider.structured(
            system="Describe the sample text the user sends. Be literal.",
            document=SAMPLE,
            schema=SmokeTest,
            task="smoke_test",
        )
    except ProjectReviveError as exc:
        print(f"FAILED  : {exc.code}")
        print(f"          {exc.message}")
        if exc.detail:
            print(f"          {exc.detail}")
        return 1

    parsed = result.parsed
    print("OK, structured output validated:")
    print(f"  language                 : {parsed.language}")
    print(f"  word_count               : {parsed.word_count}")
    print(f"  is_about_machine_learning: {parsed.is_about_machine_learning}")

    usage = result.usage
    print("\nmeasured usage:")
    print(f"  answered by : {result.model}")
    print(f"  input       : {usage.input_tokens} tokens")
    print(f"  output      : {usage.output_tokens} tokens")
    print(f"  cache read  : {usage.cached_input_tokens} tokens")

    prices = PRICES.get(result.model)
    if prices:
        cost = (
            usage.input_tokens / 1_000_000 * prices[0]
            + usage.output_tokens / 1_000_000 * prices[1]
        )
        print(f"  cost        : about ${cost:.5f} for this call")

    for warning in result.warnings:
        print(f"\nnote: {warning}")

    print("\nSet LLM_PROVIDER=anthropic in backend/.env to use it for analyses.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
