"""Current-versus-proposed stack comparison."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.analysis.gaps import analyse_gaps
from app.analysis.profile import build_profile
from app.compare.stack import compare_stack
from app.config import Settings
from app.documents.extract import extract
from app.llm.mock_provider import MockProvider
from app.recommend.engine import recommend
from app.schemas.comparison import StackEntry, StackVerdict
from app.schemas.project import Evidence
from tests.conftest import SAMPLE_PAGES, make_pdf

SETTINGS = Settings(llm_provider="mock")


def _context():
    document = extract(make_pdf(SAMPLE_PAGES), "r.pdf", SETTINGS)
    profile = build_profile(document, MockProvider()).parsed
    findings = analyse_gaps(profile, document, MockProvider()).parsed.findings
    recommendations = recommend(profile, findings, document).recommendations
    return profile, recommendations


class TestSchemaInvariants:
    def test_keeping_something_requires_showing_the_report_uses_it(self) -> None:
        with pytest.raises(ValidationError, match="must cite"):
            StackEntry(
                name="TensorFlow",
                category="library",
                verdict=StackVerdict.KEEP,
                rationale="It is fine as it is.",
            )

    def test_proposing_something_requires_naming_the_recommendation(self) -> None:
        """Nothing appears in the proposed stack without a reason attached."""
        with pytest.raises(ValidationError, match="must name the recommendation"):
            StackEntry(
                name="pytest",
                category="library",
                verdict=StackVerdict.ADD,
                rationale="Testing is good.",
            )

    def test_replacing_something_requires_saying_what(self) -> None:
        with pytest.raises(ValidationError, match="must say what it replaces"):
            StackEntry(
                name="polars",
                category="library",
                verdict=StackVerdict.REPLACE,
                introduced_by=["some-entry"],
                rationale="Faster than the alternative.",
            )


class TestComparison:
    def test_keeps_the_technologies_the_report_names(self) -> None:
        profile, recommendations = _context()
        comparison = compare_stack(profile, recommendations)

        kept = {e.name for e in comparison.of(StackVerdict.KEEP)}
        assert {"Python", "TensorFlow", "Keras"} <= kept

    def test_every_keep_cites_the_report(self) -> None:
        profile, recommendations = _context()
        for entry in compare_stack(profile, recommendations).of(StackVerdict.KEEP):
            assert entry.evidence
            assert entry.evidence[0].page >= 1

    def test_additions_are_traced_to_a_recommendation(self) -> None:
        profile, recommendations = _context()
        additions = compare_stack(profile, recommendations).of(StackVerdict.ADD)

        assert additions
        known = {r.id for r in recommendations}
        for entry in additions:
            assert entry.introduced_by
            assert set(entry.introduced_by) <= known

    def test_does_not_propose_something_the_report_already_uses(self) -> None:
        profile, recommendations = _context()
        comparison = compare_stack(profile, recommendations)

        kept = {e.name.lower() for e in comparison.of(StackVerdict.KEEP)}
        added = {e.name.lower() for e in comparison.of(StackVerdict.ADD)}
        assert kept & added == set()

    def test_nothing_is_replaced_without_a_declared_replacement(self) -> None:
        """Section 4.3 forbids calling a technology outdated for its age."""
        profile, recommendations = _context()
        for entry in compare_stack(profile, recommendations).of(
            StackVerdict.REPLACE
        ):
            assert entry.replaces

    def test_says_it_does_not_judge_technology_by_age(self) -> None:
        profile, recommendations = _context()
        notes = " ".join(compare_stack(profile, recommendations).notes).lower()
        assert "because it is old" in notes

    def test_a_duplicated_dependency_records_every_recommendation(self) -> None:
        profile, recommendations = _context()
        comparison = compare_stack(profile, recommendations)
        for entry in comparison.of(StackVerdict.ADD):
            assert len(entry.introduced_by) == len(set(entry.introduced_by))

    def test_with_no_recommendations_nothing_is_proposed(self) -> None:
        profile, _ = _context()
        comparison = compare_stack(profile, [])

        assert comparison.of(StackVerdict.ADD) == []
        assert comparison.of(StackVerdict.KEEP)
        assert any("No recommendations" in n for n in comparison.notes)

    def test_a_stack_item_without_evidence_is_not_claimed_as_kept(self) -> None:
        """A 'keep using X' for something the report may never have used."""
        from app.schemas.project import Claim, ClaimSource

        profile, recommendations = _context()
        profile.stack.tools.append(
            Claim(
                value="GuessedTool",
                source=ClaimSource.INFERRED,
                reasoning="not actually in the report",
            )
        )
        names = {e.name for e in compare_stack(profile, recommendations).entries}
        assert "GuessedTool" not in names
