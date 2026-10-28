"""Provider-independent LLM interface.

README section 5 asks for a provider-independent interface so the model can be
swapped without rewriting the application. Two rules make that work:

1. Callers never build a raw prompt string. They pass a task `system` prompt and
   the untrusted `document` text separately, so the transport layer decides how
   to isolate the document (see app/llm/sanitize.py).
2. Callers always pass a Pydantic `schema`. A provider must return a validated
   instance of it or raise; no provider hands back free-form text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class Usage:
    """Token counts, so cost can be reported from measurement, not guesswork."""

    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0


@dataclass
class StructuredResult[T: BaseModel]:
    parsed: T
    provider: str
    model: str
    usage: Usage = field(default_factory=Usage)
    warnings: list[str] = field(default_factory=list)


class LLMProvider(Protocol):
    """What the analysis pipeline depends on. Nothing else."""

    name: str
    model: str

    def structured(
        self,
        *,
        system: str,
        document: str,
        schema: type[T],
        task: str = "",
    ) -> StructuredResult[T]:
        """Return a validated `schema` instance derived from `document`."""
        ...
