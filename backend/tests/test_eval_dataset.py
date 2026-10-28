"""Consistency of the evaluation set itself.

A mislabelled or stale evaluation set produces numbers that look fine and mean
nothing. The most dangerous failure is a typo in a judged entry id: it would
silently count as grade 0, quietly penalising whichever system ranked the item
the label was meant to reward.
"""

from __future__ import annotations

from app.analysis.rules import rule_ids
from app.knowledge.loader import load_knowledge_base
from eval.run_eval import SYSTEMS, evaluate, load_cases


class TestDataset:
    def test_cases_load_and_validate(self) -> None:
        cases = load_cases()
        assert len(cases) >= 8

    def test_case_ids_are_unique(self) -> None:
        ids = [c.id for c in load_cases()]
        assert len(ids) == len(set(ids))

    def test_every_judged_entry_exists_in_the_knowledge_base(self) -> None:
        """A typo here would silently become a grade-0 label."""
        known = {e.id for e in load_knowledge_base()}
        for case in load_cases():
            unknown = set(case.judgments) - known
            assert not unknown, f"{case.id} judges unknown entries: {unknown}"

    def test_every_referenced_rule_exists(self) -> None:
        known = set(rule_ids())
        for case in load_cases():
            for finding in case.findings:
                if finding.rule_id is not None:
                    assert finding.rule_id in known, (
                        f"{case.id} references unknown rule {finding.rule_id}"
                    )

    def test_every_case_has_some_relevant_items(self) -> None:
        """A case with nothing relevant cannot discriminate between systems."""
        for case in load_cases():
            assert any(g >= 2 for g in case.judgments.values()), case.id

    def test_every_case_has_some_irrelevant_items(self) -> None:
        """Without negatives, precision cannot distinguish anything."""
        for case in load_cases():
            assert any(g == 0 for g in case.judgments.values()), (
                f"{case.id} grades nothing as irrelevant, so precision on it "
                "is uninformative"
            )

    def test_every_case_explains_its_grades(self) -> None:
        for case in load_cases():
            assert len(case.rationale) > 20, case.id

    def test_cases_convert_to_usable_profiles_and_findings(self) -> None:
        for case in load_cases():
            profile = case.project.to_profile()
            assert profile.title.value
            for finding in case.findings:
                assert finding.to_finding().title


class TestHarness:
    def test_every_system_produces_a_ranking_for_every_case(self) -> None:
        cases = load_cases()
        for name, run in SYSTEMS.items():
            for case in cases:
                ranking = run(case)
                assert isinstance(ranking, list), f"{name} on {case.id}"
                assert len(ranking) == len(set(ranking)), (
                    f"{name} returned duplicates on {case.id}"
                )

    def test_rankings_only_contain_real_entries(self) -> None:
        known = {e.id for e in load_knowledge_base()}
        for name, run in SYSTEMS.items():
            for case in load_cases():
                assert set(run(case)) <= known, name

    def test_evaluation_is_deterministic(self) -> None:
        """A changing score would make every comparison meaningless."""
        cases = load_cases()
        size = len(load_knowledge_base())
        first = {r.system: r.metrics for r in evaluate(cases, size)}
        second = {r.system: r.metrics for r in evaluate(cases, size)}
        assert first == second

    def test_all_three_systems_are_measured(self) -> None:
        """Section 8 requires comparison against at least one baseline."""
        assert set(SYSTEMS) == {"hybrid", "rules-only", "content-only"}

    def test_the_systems_actually_differ(self) -> None:
        cases = load_cases()
        results = {r.system: r.metrics for r in evaluate(cases, 22)}
        assert results["hybrid"] != results["content-only"]
