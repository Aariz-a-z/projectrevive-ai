"""Weakness and gap analysis: rules, schema invariants, and the merge step."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.analysis.gaps import analyse_gaps
from app.analysis.profile import build_profile
from app.analysis.rules import RuleContext, run_rules
from app.config import Settings
from app.documents.extract import extract
from app.llm.base import StructuredResult, Usage
from app.llm.mock_provider import MockProvider
from app.schemas.document import ExtractedDocument
from app.schemas.findings import (
    DetectedBy,
    Finding,
    FindingCategory,
    FindingKind,
    GapAnalysis,
    Severity,
)
from app.schemas.project import Evidence
from tests.conftest import SAMPLE_PAGES, make_pdf

SETTINGS = Settings(llm_provider="mock")


def _doc(pages: list[str]) -> ExtractedDocument:
    return extract(make_pdf(pages), "r.pdf", SETTINGS)


def _profile(document: ExtractedDocument):
    return build_profile(document, MockProvider()).parsed


def _findings(pages: list[str]) -> list[Finding]:
    document = _doc(pages)
    return run_rules(_profile(document), document)


def _titles(findings: list[Finding]) -> set[str]:
    return {f.rule_id or f.title for f in findings}


class TestSchemaInvariants:
    def test_a_weakness_must_quote_the_report(self) -> None:
        with pytest.raises(ValidationError, match="must quote the report"):
            Finding(
                title="Something is wrong",
                category=FindingCategory.EVALUATION,
                kind=FindingKind.WEAKNESS,
                severity=Severity.HIGH,
                explanation="This explanation is long enough to pass.",
                detected_by=DetectedBy.MODEL,
            )

    def test_a_gap_must_say_what_was_looked_for(self) -> None:
        with pytest.raises(ValidationError, match="what was looked for"):
            Finding(
                title="Something is missing",
                category=FindingCategory.TESTING,
                kind=FindingKind.GAP,
                severity=Severity.LOW,
                explanation="This explanation is long enough to pass.",
                detected_by=DetectedBy.MODEL,
            )

    def test_a_rule_finding_must_name_its_rule(self) -> None:
        with pytest.raises(ValidationError, match="rule_id"):
            Finding(
                title="Something is missing",
                category=FindingCategory.TESTING,
                kind=FindingKind.GAP,
                severity=Severity.LOW,
                explanation="This explanation is long enough to pass.",
                searched_for="looked for tests",
                detected_by=DetectedBy.RULE,
            )


class TestRuleOutputIsWellFormed:
    def test_every_rule_finding_satisfies_its_own_contract(self) -> None:
        findings = _findings(SAMPLE_PAGES)
        assert findings, "the sample report should produce findings"

        for finding in findings:
            assert finding.rule_id
            assert finding.detected_by is DetectedBy.RULE
            if finding.kind is FindingKind.WEAKNESS:
                assert finding.evidence
            else:
                assert finding.searched_for

    def test_rule_evidence_quotes_really_appear_in_the_document(self) -> None:
        document = _doc(SAMPLE_PAGES)
        for finding in run_rules(_profile(document), document):
            for item in finding.evidence:
                page = document.pages[item.page - 1].text
                assert " ".join(item.quote.split()).lower() in " ".join(
                    page.split()
                ).lower()

    def test_rules_are_deterministic(self) -> None:
        first = _titles(_findings(SAMPLE_PAGES))
        second = _titles(_findings(SAMPLE_PAGES))
        assert first == second


class TestNegationHandling:
    """A report admitting it skipped something must trigger the finding."""

    def test_no_cross_validation_triggers_rather_than_suppresses(self) -> None:
        pages = [
            "A Study",
            "We used a CNN. " * 20,
            "The model was evaluated on a train test split. "
            "No cross validation was performed. " * 3,
        ]
        assert "single-split-only" in _titles(_findings(pages))

    def test_an_affirmative_mention_does_suppress(self) -> None:
        pages = [
            "A Study",
            "We used a CNN. " * 20,
            "We performed 5-fold cross validation across the dataset. " * 3,
        ]
        assert "single-split-only" not in _titles(_findings(pages))

    def test_lack_of_is_treated_as_negation(self) -> None:
        document = _doc(["T", "There is a lack of cross validation here. " * 10])
        ctx = RuleContext(profile=_profile(document), document=document)
        assert ctx.mentions("cross validation") is False
        assert ctx.mentions("cross validation", affirmative_only=False) is True


class TestWordBoundaries:
    def test_shap_does_not_match_reshaped(self) -> None:
        """Substring matching here silently suppressed a real finding."""
        document = _doc(["T", "Images were reshaped before training. " * 10])
        ctx = RuleContext(profile=_profile(document), document=document)

        assert ctx.mentions("shap") is False
        assert "no-explainability" in _titles(
            run_rules(_profile(document), document)
        )

    def test_a_real_mention_is_still_found(self) -> None:
        document = _doc(["T", "We used SHAP values to explain predictions. " * 10])
        ctx = RuleContext(profile=_profile(document), document=document)
        assert ctx.mentions("shap") is True

    def test_stems_still_match_their_longer_forms(self) -> None:
        document = _doc(["T", "The features were normalised carefully. " * 10])
        ctx = RuleContext(profile=_profile(document), document=document)
        assert ctx.mentions("normalis") is True


class TestIndividualRules:
    def test_accuracy_alone_is_flagged(self) -> None:
        pages = [
            "A Study",
            "We trained a CNN. " * 20,
            "The model reached an accuracy of 91 percent on the test set. " * 3,
        ]
        assert "accuracy-without-class-metrics" in _titles(_findings(pages))

    def test_accuracy_with_recall_is_not_flagged(self) -> None:
        pages = [
            "A Study",
            "We trained a CNN. " * 20,
            "We report accuracy, precision and recall for every class. " * 3,
        ]
        assert "accuracy-without-class-metrics" not in _titles(_findings(pages))

    def test_resampling_without_split_order_is_flagged_as_leakage(self) -> None:
        pages = [
            "A Study",
            "We trained a CNN. " * 20,
            "We applied SMOTE to balance the dataset before modelling. " * 3,
        ]
        assert "resampling-before-split" in _titles(_findings(pages))

    def test_resampling_after_the_split_is_not_flagged(self) -> None:
        pages = [
            "A Study",
            "We trained a CNN. " * 20,
            "We applied SMOTE to the training set only, after the split. " * 3,
        ]
        assert "resampling-before-split" not in _titles(_findings(pages))

    def test_dependencies_rule_reports_missing_versions_not_old_ones(self) -> None:
        """Section 4.3 forbids calling a library outdated for being old.

        The rule fires only when versions are absent, which is a fact about
        the report rather than a judgement about the technology.
        """
        pages = [
            "A Study",
            "We built the model with TensorFlow and Keras. " * 20,
            "No version numbers are given anywhere in this report. " * 3,
        ]
        findings = _findings(pages)
        assert "unversioned-dependencies" in _titles(findings)

        finding = next(f for f in findings if f.rule_id == "unversioned-dependencies")
        assert "outdated" not in finding.explanation.lower() or (
            "not about the libraries themselves" in finding.explanation
        )


class TestMergeAndVerification:
    class _Provider:
        name = "scripted"
        model = "scripted-v1"

        def __init__(self, analysis: GapAnalysis) -> None:
            self._analysis = analysis

        def structured(self, *, system, document, schema, task=""):
            return StructuredResult(
                parsed=self._analysis,
                provider=self.name,
                model=self.model,
                usage=Usage(),
            )

    class _BrokenProvider:
        name = "broken"
        model = "broken-v1"

        def structured(self, **_kwargs):
            raise RuntimeError("model stage exploded")

    def test_model_weakness_with_a_fabricated_quote_is_dropped(self) -> None:
        document = _doc(SAMPLE_PAGES)
        invented = Finding(
            title="The authors manipulated the results",
            category=FindingCategory.EVALUATION,
            kind=FindingKind.WEAKNESS,
            severity=Severity.HIGH,
            explanation="A serious accusation with a quote that does not exist.",
            evidence=[Evidence(page=2, quote="we fabricated the numbers")],
            detected_by=DetectedBy.MODEL,
        )
        provider = self._Provider(GapAnalysis(findings=[invented]))

        report = analyse_gaps(_profile(document), document, provider).parsed

        assert all("manipulated" not in f.title for f in report.findings)
        assert any(
            "Dropped the finding" in n and "manipulated" in n
            for n in report.notes
        ), "dropping it silently would hide that the model made the claim"

    def test_model_gap_survives_without_evidence(self) -> None:
        document = _doc(SAMPLE_PAGES)
        gap = Finding(
            title="No monitoring plan for the deployed model",
            category=FindingCategory.SCALABILITY,
            kind=FindingKind.GAP,
            severity=Severity.MEDIUM,
            explanation="Nothing describes how the model would be monitored.",
            searched_for="monitoring, drift detection, alerting",
            detected_by=DetectedBy.MODEL,
        )
        provider = self._Provider(GapAnalysis(findings=[gap]))

        report = analyse_gaps(_profile(document), document, provider).parsed
        assert any(f.title.startswith("No monitoring") for f in report.findings)

    def test_a_model_finding_duplicating_a_rule_is_merged_away(self) -> None:
        document = _doc(SAMPLE_PAGES)
        duplicate = Finding(
            title="No automated tests mentioned anywhere",
            category=FindingCategory.TESTING,
            kind=FindingKind.GAP,
            severity=Severity.MEDIUM,
            explanation="Restates what the automated rule already reported.",
            searched_for="pytest, unittest",
            detected_by=DetectedBy.MODEL,
        )
        provider = self._Provider(GapAnalysis(findings=[duplicate]))

        report = analyse_gaps(_profile(document), document, provider).parsed
        testing = [
            f for f in report.findings if f.category is FindingCategory.TESTING
        ]
        assert len(testing) == 1
        assert testing[0].detected_by is DetectedBy.RULE

    def test_a_model_failure_still_returns_the_rule_findings(self) -> None:
        """The rules are independent; a model outage must not void them."""
        document = _doc(SAMPLE_PAGES)
        report = analyse_gaps(
            _profile(document), document, self._BrokenProvider()
        ).parsed

        assert report.findings, "rule findings should survive a model failure"
        assert all(f.detected_by is DetectedBy.RULE for f in report.findings)
        assert any("model stage" in n for n in report.notes)

    def test_findings_are_ordered_by_severity(self) -> None:
        document = _doc(SAMPLE_PAGES)
        report = analyse_gaps(_profile(document), document, MockProvider()).parsed
        order = [f.severity.value for f in report.findings]
        rank = {"high": 0, "medium": 1, "low": 2}
        assert order == sorted(order, key=lambda s: rank[s])


class TestMockProvider:
    def test_mock_adds_no_findings_but_says_so(self) -> None:
        """Inventing criticism of someone's work would be worse than silence."""
        document = _doc(SAMPLE_PAGES)
        report = analyse_gaps(_profile(document), document, MockProvider()).parsed

        assert all(f.detected_by is DetectedBy.RULE for f in report.findings)
        assert any("mock provider" in n.lower() for n in report.notes)

    def test_rules_still_produce_useful_output_without_a_model(self) -> None:
        document = _doc(SAMPLE_PAGES)
        report = analyse_gaps(_profile(document), document, MockProvider()).parsed

        assert len(report.findings) >= 4
        assert report.by_severity()["high"] >= 1
