"""Ranking metrics, checked against values computed by hand.

These are the numbers that would appear in a report, so a silent error here
would not crash anything -- it would produce a confident, wrong conclusion.
Every expected value below is worked out in the comment beside it rather than
copied from the implementation being tested.
"""

from __future__ import annotations

import math

import pytest

from eval.metrics import (
    catalogue_coverage,
    dcg_at_k,
    mean,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)

# grade 3 = clearly right, 2 = useful, 0 = irrelevant
JUDGMENTS = {"a": 3, "b": 0, "c": 2}


class TestPrecision:
    def test_counts_only_grades_at_or_above_two(self) -> None:
        # top 3 = a(3) hit, b(0) miss, c(2) hit -> 2/3
        assert precision_at_k(["a", "b", "c"], JUDGMENTS, 3) == pytest.approx(2 / 3)

    def test_unjudged_items_count_as_irrelevant(self) -> None:
        # "z" is absent from the judgments, so grade 0 -> 1/2
        assert precision_at_k(["a", "z"], JUDGMENTS, 2) == pytest.approx(0.5)

    def test_denominator_is_k_not_the_list_length(self) -> None:
        """Returning fewer items than asked for is not perfect precision."""
        # one relevant item returned, k=5 -> 1/5, not 1/1
        assert precision_at_k(["a"], JUDGMENTS, 5) == pytest.approx(0.2)

    def test_grade_one_does_not_count_as_relevant(self) -> None:
        assert precision_at_k(["m"], {"m": 1}, 1) == 0.0

    def test_zero_k(self) -> None:
        assert precision_at_k(["a"], JUDGMENTS, 0) == 0.0


class TestRecall:
    def test_share_of_relevant_items_found(self) -> None:
        # relevant = {a, c}; top 2 = [a, b] finds a -> 1/2
        assert recall_at_k(["a", "b"], JUDGMENTS, 2) == pytest.approx(0.5)

    def test_all_relevant_found(self) -> None:
        assert recall_at_k(["a", "c"], JUDGMENTS, 2) == pytest.approx(1.0)

    def test_no_relevant_items_at_all(self) -> None:
        assert recall_at_k(["a"], {"a": 0}, 1) == 0.0


class TestDcg:
    def test_matches_a_hand_computed_value(self) -> None:
        # ranks 1..3 with grades 3, 0, 2:
        #   (2^3-1)/log2(2) = 7/1   = 7.0
        #   (2^0-1)/log2(3) = 0     = 0.0
        #   (2^2-1)/log2(4) = 3/2   = 1.5
        #                            = 8.5
        assert dcg_at_k(["a", "b", "c"], JUDGMENTS, 3) == pytest.approx(8.5)

    def test_position_matters(self) -> None:
        """The same items ranked worse must score lower."""
        better = dcg_at_k(["a", "c"], JUDGMENTS, 2)
        worse = dcg_at_k(["c", "a"], JUDGMENTS, 2)
        assert better > worse

    def test_k_truncates(self) -> None:
        # only the first item counts: 7.0
        assert dcg_at_k(["a", "c"], JUDGMENTS, 1) == pytest.approx(7.0)


class TestNdcg:
    def test_perfect_ranking_scores_one(self) -> None:
        assert ndcg_at_k(["a", "c", "b"], JUDGMENTS, 3) == pytest.approx(1.0)

    def test_matches_a_hand_computed_value(self) -> None:
        # DCG  = 8.5 (above)
        # ideal grades ordered 3, 2, 0:
        #   7/log2(2) + 3/log2(3) + 0 = 7 + 1.8927892... = 8.8927892...
        ideal = 7 + 3 / math.log2(3)
        assert ndcg_at_k(["a", "b", "c"], JUDGMENTS, 3) == pytest.approx(8.5 / ideal)

    def test_worst_ranking_scores_lowest(self) -> None:
        worst = ndcg_at_k(["b", "c", "a"], JUDGMENTS, 3)
        best = ndcg_at_k(["a", "c", "b"], JUDGMENTS, 3)
        assert 0.0 < worst < best

    def test_is_bounded(self) -> None:
        for order in (["a", "b", "c"], ["c", "b", "a"], ["b", "a", "c"]):
            assert 0.0 <= ndcg_at_k(order, JUDGMENTS, 3) <= 1.0

    def test_no_relevant_items_gives_zero_not_a_crash(self) -> None:
        assert ndcg_at_k(["a"], {"a": 0}, 3) == 0.0

    def test_graded_relevance_actually_distinguishes(self) -> None:
        """Putting the grade-3 item first must beat putting grade-2 first."""
        judgments = {"top": 3, "ok": 2}
        assert ndcg_at_k(["top", "ok"], judgments, 2) > ndcg_at_k(
            ["ok", "top"], judgments, 2
        )


class TestCoverage:
    def test_counts_distinct_items_across_cases(self) -> None:
        # {a, b} from one case and {c, d} from another = 4 of 10
        assert catalogue_coverage(
            [["a", "b"], ["c", "d"]], catalogue_size=10, k=2
        ) == pytest.approx(0.4)

    def test_repeating_the_same_items_does_not_raise_coverage(self) -> None:
        """A recommender returning the same three items always scores low."""
        assert catalogue_coverage(
            [["a", "b"], ["a", "b"], ["a", "b"]], catalogue_size=10, k=2
        ) == pytest.approx(0.2)

    def test_respects_k(self) -> None:
        assert catalogue_coverage(
            [["a", "b", "c"]], catalogue_size=10, k=1
        ) == pytest.approx(0.1)

    def test_empty_catalogue(self) -> None:
        assert catalogue_coverage([["a"]], catalogue_size=0, k=1) == 0.0


class TestMean:
    def test_averages(self) -> None:
        assert mean([0.0, 0.5, 1.0]) == pytest.approx(0.5)

    def test_empty_is_zero_not_a_crash(self) -> None:
        assert mean([]) == 0.0
