"""The hybrid recommendation engine: knowledge base, matching, ranking."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.analysis.gaps import analyse_gaps
from app.analysis.profile import build_profile
from app.analysis.rules import rule_ids
from app.config import Settings
from app.documents.extract import extract
from app.knowledge.loader import load_knowledge_base
from app.llm.mock_provider import MockProvider
from app.recommend import baselines
from app.recommend.engine import infer_constraints, recommend
from app.recommend.matching import (
    CONTENT_ONLY_CEILING,
    Candidate,
    _relative_scores,
)
from app.recommend.rank import assess_feasibility, score_candidate
from app.schemas.findings import Finding
from app.schemas.recommendation import (
    CostBand,
    MatchedBy,
    Recommendation,
    ScoreBreakdown,
    SkillLevel,
    UserConstraints,
    Weights,
)
from tests.conftest import SAMPLE_PAGES, make_pdf

SETTINGS = Settings(llm_provider="mock")


def _context():
    document = extract(make_pdf(SAMPLE_PAGES), "r.pdf", SETTINGS)
    profile = build_profile(document, MockProvider()).parsed
    findings = analyse_gaps(profile, document, MockProvider()).parsed.findings
    return profile, findings, document


class TestKnowledgeBase:
    def test_loads_and_validates(self) -> None:
        entries = load_knowledge_base()
        assert len(entries) >= 20

    def test_ids_are_unique(self) -> None:
        ids = [e.id for e in load_knowledge_base()]
        assert len(ids) == len(set(ids))

    def test_every_entry_states_a_trade_off(self) -> None:
        """A recommendation with no stated downside is advertising."""
        for entry in load_knowledge_base():
            assert entry.trade_offs, f"{entry.id} states no trade-offs"
            assert all(t.strip() for t in entry.trade_offs)

    def test_every_entry_says_how_to_validate_it(self) -> None:
        for entry in load_knowledge_base():
            assert len(entry.validation_method) > 10, entry.id

    def test_every_rule_has_at_least_one_recommendation(self) -> None:
        """A rule that detects a problem nothing can fix is a dead end."""
        covered: set[str] = set()
        for entry in load_knowledge_base():
            covered |= set(entry.addresses_rules)
        assert set(rule_ids()) - covered == set()

    def test_entries_only_reference_rules_that_exist(self) -> None:
        known = set(rule_ids())
        for entry in load_knowledge_base():
            unknown = set(entry.addresses_rules) - known
            assert not unknown, f"{entry.id} references unknown rules {unknown}"


class TestRecommendationSchema:
    def _score(self) -> ScoreBreakdown:
        return ScoreBreakdown(
            relevance=0.5,
            feasibility=1.0,
            expected_impact=0.5,
            effort_penalty=0.2,
            cost_penalty=0.0,
            weights=Weights().as_dict(),
            final=0.5,
        )

    def test_a_recommendation_without_trade_offs_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="trade-offs"):
            Recommendation(
                id="x",
                title="Do the thing",
                problem_addressed="p",
                current_approach="c",
                proposed_approach="a",
                reason="r",
                complexity="low",
                cost="none",
                skill_level="beginner",
                validation_method="check it",
                matched_by=MatchedBy.KNOWLEDGE,
                score=self._score(),
                trade_offs=[],
            )


class TestRelativeScoring:
    def test_scores_are_scaled_against_the_best_match(self) -> None:
        assert _relative_scores([0.05, 0.10, 0.025]) == [0.5, 1.0, 0.25]

    def test_scale_does_not_change_the_result(self) -> None:
        """TF-IDF and transformer cosines live on different scales."""
        tfidf_like = _relative_scores([0.02, 0.10, 0.06])
        transformer_like = _relative_scores([0.2, 1.0, 0.6])
        assert tfidf_like == pytest.approx(transformer_like)

    def test_an_entirely_unrelated_corpus_scores_zero(self) -> None:
        assert _relative_scores([0.0001, 0.0002]) == [0.0, 0.0]

    def test_empty_input(self) -> None:
        assert _relative_scores([]) == []


class TestRelevance:
    def _candidate(self, knowledge: float, content: float) -> Candidate:
        return Candidate(
            entry=load_knowledge_base()[0],
            knowledge_score=knowledge,
            content_score=content,
        )

    def test_content_only_is_capped_below_a_knowledge_match(self) -> None:
        """A lexical coincidence must not outrank a cited finding."""
        content_only = self._candidate(0.0, 1.0)
        knowledge_backed = self._candidate(1.0, 0.0)

        assert content_only.relevance <= CONTENT_ONLY_CEILING
        assert knowledge_backed.relevance > content_only.relevance

    def test_match_source_is_reported(self) -> None:
        assert self._candidate(1.0, 0.0).matched_by is MatchedBy.KNOWLEDGE
        assert self._candidate(0.0, 0.9).matched_by is MatchedBy.CONTENT
        assert self._candidate(1.0, 0.9).matched_by is MatchedBy.BOTH


class TestFeasibilityAndConstraints:
    def _entry(self, **overrides):
        entry = load_knowledge_base()[0]
        return entry.model_copy(update=overrides)

    def test_gpu_requirement_excludes_rather_than_demotes(self) -> None:
        """Section 7: unavailable hardware must not simply rank lower."""
        entry = self._entry(requires_gpu=True)
        result = assess_feasibility(entry, UserConstraints(has_gpu=False))

        assert result.is_possible is False
        assert "GPU" in (result.excluded_reason or "")

    def test_gpu_requirement_is_fine_when_a_gpu_is_available(self) -> None:
        entry = self._entry(requires_gpu=True)
        assert assess_feasibility(entry, UserConstraints(has_gpu=True)).is_possible

    def test_dataset_size_requirement_excludes(self) -> None:
        entry = self._entry(min_dataset_rows=100_000)
        result = assess_feasibility(entry, UserConstraints(dataset_rows=500))

        assert result.is_possible is False
        assert "100,000" in (result.excluded_reason or "")

    def test_unknown_dataset_size_does_not_exclude(self) -> None:
        """Guessing a project is too small would hide valid advice."""
        entry = self._entry(min_dataset_rows=100_000)
        assert assess_feasibility(
            entry, UserConstraints(dataset_rows=None)
        ).is_possible

    def test_skill_gap_reduces_feasibility_and_explains_why(self) -> None:
        entry = self._entry(skill_level=SkillLevel.ADVANCED)
        result = assess_feasibility(
            entry, UserConstraints(skill_level=SkillLevel.BEGINNER)
        )
        assert result.score < 1.0
        assert any("advanced" in note for note in result.notes)

    def test_cost_above_budget_reduces_feasibility(self) -> None:
        entry = self._entry(cost=CostBand.HIGH)
        result = assess_feasibility(entry, UserConstraints(budget=CostBand.NONE))
        assert result.score < 1.0
        assert result.notes


class TestScoring:
    def _candidate(self, **overrides) -> Candidate:
        entry = load_knowledge_base()[0].model_copy(update=overrides)
        return Candidate(entry=entry, knowledge_score=1.0, content_score=0.5)

    def test_final_score_stays_in_range(self) -> None:
        breakdown, _ = score_candidate(
            self._candidate(), UserConstraints(), Weights()
        )
        assert 0.0 <= breakdown.final <= 1.0

    def test_the_weights_used_are_reported(self) -> None:
        """Section 4.4: a score must not look like a measurement."""
        weights = Weights(relevance=0.5, impact=0.3)
        breakdown, _ = score_candidate(
            self._candidate(), UserConstraints(), weights
        )
        assert breakdown.weights["relevance"] == 0.5
        assert "relevance" in breakdown.formula

    def test_higher_impact_scores_higher(self) -> None:
        low, _ = score_candidate(
            self._candidate(impact=0.1), UserConstraints(), Weights()
        )
        high, _ = score_candidate(
            self._candidate(impact=0.9), UserConstraints(), Weights()
        )
        assert high.final > low.final

    def test_higher_effort_scores_lower(self) -> None:
        easy, _ = score_candidate(
            self._candidate(complexity="low"), UserConstraints(), Weights()
        )
        hard, _ = score_candidate(
            self._candidate(complexity="high"), UserConstraints(), Weights()
        )
        assert easy.final > hard.final

    def test_reweighting_changes_the_outcome(self) -> None:
        """The weights must actually be configurable, not decorative."""
        candidate = self._candidate(impact=0.9, complexity="high")
        impact_led, _ = score_candidate(
            candidate, UserConstraints(), Weights(impact=0.8, effort=0.0)
        )
        effort_led, _ = score_candidate(
            candidate, UserConstraints(), Weights(impact=0.1, effort=0.8)
        )
        assert impact_led.final > effort_led.final


class TestEngine:
    def test_produces_ranked_recommendations_for_the_sample_report(self) -> None:
        profile, findings, document = _context()
        report = recommend(profile, findings, document)

        assert report.recommendations
        scores = [r.score.final for r in report.recommendations]
        assert scores == sorted(scores, reverse=True)

    def test_top_recommendations_cite_the_users_own_report(self) -> None:
        profile, findings, document = _context()
        report = recommend(profile, findings, document)

        cited = [r for r in report.recommendations if r.evidence]
        assert cited, "recommendations should carry evidence from the findings"
        for item in cited:
            for quote in item.evidence:
                assert 1 <= quote.page <= document.page_count

    def test_recommendations_address_detected_findings(self) -> None:
        profile, findings, document = _context()
        report = recommend(profile, findings, document)

        titles = {f.title for f in findings}
        linked = [
            r for r in report.recommendations if set(r.addresses_findings) & titles
        ]
        assert linked

    def test_every_recommendation_carries_the_required_fields(self) -> None:
        profile, findings, document = _context()
        for item in recommend(profile, findings, document).recommendations:
            assert item.trade_offs
            assert item.expected_benefits
            assert item.implementation_steps
            assert item.validation_method
            assert item.score.weights

    def test_is_deterministic(self) -> None:
        profile, findings, document = _context()
        first = recommend(profile, findings, document)
        second = recommend(profile, findings, document)
        assert [r.id for r in first.recommendations] == [
            r.id for r in second.recommendations
        ]

    def test_reports_its_assumptions(self) -> None:
        """Feasibility from a guess must not look like feasibility from fact."""
        profile, findings, document = _context()
        report = recommend(profile, findings, document)

        assert report.constraints.assumptions
        assert any("assumed" in a.lower() for a in report.constraints.assumptions)

    def test_says_the_impact_figure_is_an_estimate(self) -> None:
        profile, findings, document = _context()
        report = recommend(profile, findings, document)
        assert any("estimate" in note.lower() for note in report.notes)

    def test_with_no_findings_it_says_the_matches_are_weaker(self) -> None:
        profile, _, document = _context()
        report = recommend(profile, [], document)
        assert any("similarity alone" in note for note in report.notes)

    def test_a_gpu_constraint_excludes_with_a_reason(self) -> None:
        profile, findings, document = _context()
        report = recommend(
            profile,
            findings,
            document,
            constraints=UserConstraints(has_gpu=False),
        )
        ids = {r.id for r in report.recommendations}
        for entry in load_knowledge_base():
            if entry.requires_gpu:
                assert entry.id not in ids


class TestConstraintInference:
    def test_detects_a_mentioned_gpu(self) -> None:
        document = extract(
            make_pdf(["T", "Training ran on an NVIDIA GPU with CUDA. " * 10]),
            "r.pdf",
            SETTINGS,
        )
        profile = build_profile(document, MockProvider()).parsed
        assert infer_constraints(profile, document).has_gpu is True

    def test_assumes_no_gpu_when_unmentioned(self) -> None:
        profile, _, document = _context()
        constraints = infer_constraints(profile, document)
        assert constraints.has_gpu is False
        assert any("No GPU was assumed" in a for a in constraints.assumptions)

    def test_reads_a_dataset_size_when_stated(self) -> None:
        document = extract(
            make_pdf(["T", "The dataset contains 60,000 images in total. " * 10]),
            "r.pdf",
            SETTINGS,
        )
        profile = build_profile(document, MockProvider()).parsed
        assert infer_constraints(profile, document).dataset_rows == 60_000


class TestBaselines:
    def test_rules_only_returns_entries_linked_to_findings(self) -> None:
        profile, findings, _ = _context()
        result = baselines.rules_only(profile, findings)
        assert result
        assert len(result) == len(set(result))

    def test_content_only_ignores_findings_entirely(self) -> None:
        profile, findings, _ = _context()
        with_findings = baselines.content_only(profile, findings)
        without = baselines.content_only(profile, [])
        assert with_findings == without

    def test_the_two_baselines_differ(self) -> None:
        """If they agreed, comparing the hybrid against both would be pointless."""
        profile, findings, _ = _context()
        assert baselines.rules_only(profile, findings) != baselines.content_only(
            profile, findings
        )
