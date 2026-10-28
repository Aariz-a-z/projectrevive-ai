"""Ranking metrics for recommendation quality.

Standard definitions, implemented directly rather than pulled from a library
so the exact formula used to produce a published number is readable here.
Every function is tested against hand-computed values in
tests/test_eval_metrics.py -- a quietly wrong NDCG would not crash anything,
it would just produce a confident conclusion that happens to be false.

Relevance is graded 0-3 rather than binary:

    3  clearly the right advice for this project
    2  useful and appropriate
    1  marginal; not wrong but not a priority
    0  irrelevant, or actively unsuitable

Binary metrics (precision, recall) treat >= 2 as relevant. NDCG uses the full
grade, which is the point of grading: it distinguishes a ranking that puts the
best item first from one that merely puts a relevant item first.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence

#: Grade at or above which an item counts as relevant for binary metrics.
RELEVANCE_THRESHOLD = 2


def precision_at_k(
    ranked: Sequence[str], judgments: Mapping[str, int], k: int
) -> float:
    """Share of the top k that is relevant.

    The denominator is k, not len(ranked). A system returning three good items
    when ten were asked for has not achieved perfect precision; it has
    under-delivered, and dividing by the shorter list would hide that.
    """
    if k <= 0:
        return 0.0
    top = ranked[:k]
    hits = sum(1 for item in top if judgments.get(item, 0) >= RELEVANCE_THRESHOLD)
    return hits / k


def recall_at_k(
    ranked: Sequence[str], judgments: Mapping[str, int], k: int
) -> float:
    """Share of all relevant items that appear in the top k."""
    relevant = {
        item for item, grade in judgments.items() if grade >= RELEVANCE_THRESHOLD
    }
    if not relevant:
        return 0.0
    found = sum(1 for item in ranked[:k] if item in relevant)
    return found / len(relevant)


def dcg_at_k(
    ranked: Sequence[str], judgments: Mapping[str, int], k: int
) -> float:
    """Discounted cumulative gain, exponential-gain form.

    gain = (2**grade - 1) / log2(rank + 1), ranks starting at 1. The
    exponential form is used because it rewards getting a grade-3 item into
    the top slot much more than a grade-1 item, which is the behaviour being
    measured.
    """
    total = 0.0
    for index, item in enumerate(ranked[:k], start=1):
        grade = judgments.get(item, 0)
        if grade > 0:
            total += (2**grade - 1) / math.log2(index + 1)
    return total


def ndcg_at_k(
    ranked: Sequence[str], judgments: Mapping[str, int], k: int
) -> float:
    """DCG divided by the DCG of the best possible ranking of the same items."""
    ideal_order = sorted(judgments.values(), reverse=True)[:k]
    ideal = sum(
        (2**grade - 1) / math.log2(index + 1)
        for index, grade in enumerate(ideal_order, start=1)
        if grade > 0
    )
    if ideal == 0:
        return 0.0
    return dcg_at_k(ranked, judgments, k) / ideal


def catalogue_coverage(
    rankings: Iterable[Sequence[str]], catalogue_size: int, k: int
) -> float:
    """Share of the catalogue that appears in any case's top k.

    Low coverage means the system recommends the same few items regardless of
    input, which precision and NDCG cannot detect -- a recommender that always
    returns the three most generally useful entries can score well on both.
    """
    if catalogue_size <= 0:
        return 0.0
    seen: set[str] = set()
    for ranking in rankings:
        seen.update(ranking[:k])
    return len(seen) / catalogue_size


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0
