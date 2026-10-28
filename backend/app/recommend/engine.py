"""Turning findings into ranked, explained recommendations.

The pipeline is deliberately boring: match, score, exclude the impossible,
sort, and build an explanation object carrying every field README section 4.4
requires. Nothing here is learned; the ordering is entirely determined by the
knowledge base and the weights, both of which are visible to the user.

Constraints are inferred rather than asked for, because nothing collects them
yet. Every inference is recorded in `UserConstraints.assumptions` and shown in
the UI, so a feasibility score computed from a guess is never mistaken for one
computed from fact.
"""

from __future__ import annotations

import logging
import re

from app.knowledge.loader import load_knowledge_base
from app.recommend.embed import get_embedder
from app.recommend.matching import Candidate, find_candidates
from app.recommend.rank import score_candidate
from app.schemas.document import ExtractedDocument
from app.schemas.findings import Finding
from app.schemas.project import Evidence, ProjectProfile
from app.schemas.recommendation import (
    CostBand,
    Recommendation,
    RecommendationReport,
    SkillLevel,
    UserConstraints,
    Weights,
)

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 12

GPU_TERMS = ("gpu", "cuda", "nvidia", "tesla v100", "rtx", "tpu", "colab")
# "12,000 images", "5000 samples", "1.2 million records"
_ROW_COUNT = re.compile(
    r"\b([\d][\d,\.]{2,})\s*(?:k\b|thousand|million)?\s*"
    r"(images|samples|rows|records|instances|examples|documents|tweets)\b",
    re.I,
)


def infer_constraints(
    profile: ProjectProfile, document: ExtractedDocument
) -> UserConstraints:
    """Best guess at what this project can do, with every guess recorded."""
    text = document.full_text.lower()
    assumptions: list[str] = []

    has_gpu = any(term in text for term in GPU_TERMS)
    assumptions.append(
        "GPU access was inferred from the report mentioning one."
        if has_gpu
        else "No GPU was assumed, because the report does not mention one. "
        "Recommendations needing one were excluded."
    )

    dataset_rows: int | None = None
    match = _ROW_COUNT.search(text)
    if match:
        raw = match.group(1).replace(",", "")
        try:
            value = float(raw)
        except ValueError:
            value = 0.0
        tail = match.group(0).lower()
        if "million" in tail:
            value *= 1_000_000
        elif re.search(r"\dk\b", tail) or "thousand" in tail:
            value *= 1_000
        if value >= 1:
            dataset_rows = int(value)
            assumptions.append(
                f"Dataset size read as roughly {dataset_rows:,} from the "
                f"phrase {match.group(0).strip()!r}."
            )
    if dataset_rows is None:
        assumptions.append(
            "Dataset size could not be determined, so no size-based "
            "recommendation was excluded."
        )

    assumptions.append(
        "Intermediate skill level and a low budget were assumed; nothing "
        "collects these yet."
    )

    return UserConstraints(
        has_gpu=has_gpu,
        dataset_rows=dataset_rows,
        skill_level=SkillLevel.INTERMEDIATE,
        budget=CostBand.LOW,
        needs_deployment=True,
        assumptions=assumptions,
    )


def _evidence_for(candidate: Candidate) -> list[Evidence]:
    """Citations from the findings behind this recommendation, deduplicated."""
    seen: set[tuple[int, str]] = set()
    evidence: list[Evidence] = []
    for finding in candidate.matched_findings:
        for item in finding.evidence:
            key = (item.page, item.quote)
            if key in seen:
                continue
            seen.add(key)
            evidence.append(item)
    return evidence[:3]


def _build(candidate: Candidate, breakdown, feasibility) -> Recommendation:
    entry = candidate.entry
    return Recommendation(
        id=entry.id,
        title=entry.title,
        problem_addressed=entry.problem,
        current_approach=entry.current_approach,
        proposed_approach=entry.proposed_approach,
        reason=entry.reason,
        evidence=_evidence_for(candidate),
        addresses_findings=[f.title for f in candidate.matched_findings],
        expected_benefits=entry.expected_benefits,
        trade_offs=entry.trade_offs,
        complexity=entry.complexity,
        cost=entry.cost,
        skill_level=entry.skill_level,
        dependencies=entry.dependencies,
        implementation_steps=entry.implementation_steps,
        validation_method=entry.validation_method,
        matched_by=candidate.matched_by,
        score=breakdown,
        constraint_notes=feasibility.notes,
    )


def recommend(
    profile: ProjectProfile,
    findings: list[Finding],
    document: ExtractedDocument,
    *,
    embedder_name: str = "tfidf",
    weights: Weights | None = None,
    constraints: UserConstraints | None = None,
    limit: int = DEFAULT_LIMIT,
) -> RecommendationReport:
    weights = weights or Weights()
    constraints = constraints or infer_constraints(profile, document)
    entries = load_knowledge_base()
    embedder = get_embedder(embedder_name)

    candidates = find_candidates(profile, findings, entries, embedder)
    logger.info("%d candidate(s) from %d entries", len(candidates), len(entries))

    recommendations: list[Recommendation] = []
    excluded: list[str] = []

    for candidate in candidates:
        breakdown, feasibility = score_candidate(candidate, constraints, weights)
        if not feasibility.is_possible:
            excluded.append(
                f"{candidate.entry.title} — {feasibility.excluded_reason}"
            )
            continue
        recommendations.append(_build(candidate, breakdown, feasibility))

    recommendations.sort(key=lambda r: r.score.final, reverse=True)

    notes: list[str] = [
        "Scores are a weighted sum of relevance, feasibility and an estimated "
        "impact, minus effort and cost. The weights are shown with each score "
        "and are a starting point, not a validated model.",
        "Expected impact is a hand-written estimate in the knowledge base, the "
        "same for every project matching that entry. It has not been measured.",
    ]
    if len(recommendations) > limit:
        notes.append(
            f"{len(recommendations) - limit} further recommendation(s) scored "
            "below the cut-off and are not shown."
        )
        recommendations = recommendations[:limit]

    if not findings:
        notes.append(
            "No weaknesses or gaps were detected, so these matched on project "
            "similarity alone and are weaker suggestions than usual."
        )

    return RecommendationReport(
        recommendations=recommendations,
        weights=weights,
        constraints=constraints,
        notes=notes,
        excluded=excluded,
    )
