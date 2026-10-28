"""Simpler recommenders, for honest comparison.

README section 8 requires the hybrid engine to be measured against at least one
simpler baseline, and to report the result even when the hybrid does not win.
These are the two obvious ablations, each a real implementation rather than a
strawman built to lose:

- `rules_only`: knowledge linkage alone. Ignores text similarity entirely and
  orders by how strongly a detected finding points at an entry.
- `content_only`: similarity alone. Ignores findings entirely, which is what a
  pure content-based recommender would do.

The hybrid is the combination. If it does not beat both of these on the
evaluation set, that is a finding about the hybrid, not about the baselines.
"""

from __future__ import annotations

from app.knowledge.loader import load_knowledge_base
from app.recommend.embed import get_embedder, normalise
from app.recommend.matching import (
    SEVERITY_WEIGHT,
    LINK_CATEGORY,
    LINK_RULE,
    project_text,
)
from app.schemas.findings import Finding
from app.schemas.project import ProjectProfile


def rules_only(
    profile: ProjectProfile, findings: list[Finding], limit: int = 12
) -> list[str]:
    """Entry ids ranked by knowledge linkage alone. Returns ids, not objects."""
    entries = load_knowledge_base()
    scored: list[tuple[float, str]] = []

    for entry in entries:
        best = 0.0
        for finding in findings:
            if finding.rule_id and finding.rule_id in entry.addresses_rules:
                strength = LINK_RULE
            elif finding.category in entry.addresses_categories:
                strength = LINK_CATEGORY
            elif finding.category is entry.category:
                strength = LINK_CATEGORY
            else:
                continue
            best = max(best, strength * SEVERITY_WEIGHT[finding.severity])

        if best > 0:
            # Impact breaks ties, so the ordering is deterministic.
            scored.append((best + 0.001 * entry.impact, entry.id))

    scored.sort(reverse=True)
    return [entry_id for _, entry_id in scored[:limit]]


def content_only(
    profile: ProjectProfile,
    findings: list[Finding],
    limit: int = 12,
    embedder_name: str = "tfidf",
) -> list[str]:
    """Entry ids ranked by text similarity alone, ignoring every finding."""
    entries = load_knowledge_base()
    embedder = get_embedder(embedder_name)

    query = project_text(profile, findings=[])
    documents = [normalise(entry.match_text()) for entry in entries]
    similarities = embedder.similarities(query, documents)

    ranked = sorted(
        zip(similarities, [e.id for e in entries], strict=True), reverse=True
    )
    return [entry_id for score, entry_id in ranked[:limit] if score > 0]
