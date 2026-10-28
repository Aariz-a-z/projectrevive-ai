"""Loading and validating the knowledge base.

Validation happens once at import and raises on a bad entry. A malformed YAML
file should stop the service starting, not surface as a confusing failure in
the middle of someone's analysis.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.knowledge.schema import KBEntry

logger = logging.getLogger(__name__)

KB_DIR = Path(__file__).parent / "kb"


class KnowledgeBaseError(RuntimeError):
    """The knowledge base on disk is not usable."""


def _load_file(path: Path) -> list[KBEntry]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(raw, list):
        raise KnowledgeBaseError(
            f"{path.name}: expected a list of entries, got {type(raw).__name__}"
        )

    entries: list[KBEntry] = []
    for index, item in enumerate(raw):
        try:
            entries.append(KBEntry.model_validate(item))
        except ValidationError as exc:
            name = item.get("id", f"#{index}") if isinstance(item, dict) else f"#{index}"
            raise KnowledgeBaseError(
                f"{path.name}: entry {name} is invalid:\n{exc}"
            ) from exc
    return entries


@lru_cache(maxsize=1)
def load_knowledge_base() -> tuple[KBEntry, ...]:
    """Every entry, validated, with ids checked for collisions."""
    if not KB_DIR.is_dir():
        raise KnowledgeBaseError(f"knowledge base directory missing: {KB_DIR}")

    entries: list[KBEntry] = []
    for path in sorted(KB_DIR.glob("*.yaml")):
        entries.extend(_load_file(path))

    seen: dict[str, str] = {}
    for entry in entries:
        if entry.id in seen:
            raise KnowledgeBaseError(
                f"duplicate knowledge base id {entry.id!r}; ids must be unique "
                "because recommendations are deduplicated by them"
            )
        seen[entry.id] = entry.title

    if not entries:
        raise KnowledgeBaseError(f"no knowledge base entries found in {KB_DIR}")

    logger.info("loaded %d knowledge base entries", len(entries))
    return tuple(entries)


def entries_for_rule(rule_id: str) -> list[KBEntry]:
    return [e for e in load_knowledge_base() if rule_id in e.addresses_rules]
