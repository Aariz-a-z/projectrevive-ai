"""Deterministic weakness and gap detectors.

These run over the structured profile and the document text, with no model
involved. That matters for three reasons: they cannot hallucinate, they are
readable so a user can judge whether a finding is fair, and they are cheap, so
the gap analysis still produces something useful with no API key configured.

Every gap records the terms it searched for. A reader who disagrees with a
finding can see exactly what was looked for and decide the search was too
narrow, which is not possible with a model's judgement alone.

A deliberate omission: there is no rule that flags a library as outdated for
being old. README section 4.3 forbids calling a technique inadequate merely
because something newer exists, and a rule firing on a version number would do
exactly that. `unversioned_dependencies` instead reports when currency cannot
be assessed at all, which is a fact about the report rather than a judgement
about the technology.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache

from app.schemas.document import ExtractedDocument
from app.schemas.findings import (
    DetectedBy,
    Finding,
    FindingCategory,
    FindingKind,
    Severity,
)
from app.schemas.project import Evidence, ProjectProfile


# How far back to look for a negation before a matched term.
NEGATION_WINDOW = 45
NEGATION_MARKERS = (
    "no ", "not ", "without ", "lack of", "lacks ", "lacking", "absent",
    "never ", "did not", "was not", "were not", "neither ", "none of",
    "failed to", "omitted", "missing",
)


@lru_cache(maxsize=512)
def _term_pattern(term: str) -> re.Pattern[str]:
    r"""Match a term at a word start, but allow it to be a stem.

    A leading \b only. Without it "shap" matches inside "reshaped", which
    silently suppresses the explainability finding for any report that
    mentions reshaping. Leaving the trailing boundary off is deliberate, so
    deliberate stems such as "interpretab" still match "interpretability".
    """
    return re.compile(r"\b" + re.escape(term.lower()))


@dataclass
class RuleContext:
    profile: ProjectProfile
    document: ExtractedDocument

    def __post_init__(self) -> None:
        self._pages = [
            (p.page_number, " ".join(p.text.split())) for p in self.document.pages
        ]
        self._blob = " ".join(text for _, text in self._pages).lower()

    def mentions(self, *terms: str, affirmative_only: bool = True) -> bool:
        """Whether the report mentions any term, by default only positively.

        Plain substring matching reads "no cross validation was performed" as
        evidence that cross-validation happened, which silences exactly the
        finding that sentence should trigger. A term is treated as mentioned
        only if at least one occurrence is not immediately negated.
        """
        for term in terms:
            for match in _term_pattern(term).finditer(self._blob):
                if affirmative_only and self._is_negated(match.start()):
                    continue
                return True
        return False

    def _is_negated(self, position: int) -> bool:
        window = self._blob[max(0, position - NEGATION_WINDOW) : position]
        return any(marker in window for marker in NEGATION_MARKERS)

    def quote_for(self, *terms: str) -> Evidence | None:
        """First sentence mentioning any term, as a citable quote."""
        patterns = [_term_pattern(t) for t in terms]
        for page_number, text in self._pages:
            for sentence in re.split(r"(?<=[.!?])\s+", text):
                low = sentence.lower()
                if any(p.search(low) for p in patterns):
                    return Evidence(page=page_number, quote=sentence[:600])
        return None

    def metric_values(self) -> set[str]:
        return {c.value.lower() for c in self.profile.evaluation.metrics}


Rule = Callable[[RuleContext], Finding | None]
_RULES: list[tuple[str, Rule]] = []


def rule(rule_id: str) -> Callable[[Rule], Rule]:
    def register(fn: Rule) -> Rule:
        _RULES.append((rule_id, fn))
        return fn

    return register


def _gap(
    rule_id: str,
    title: str,
    category: FindingCategory,
    severity: Severity,
    explanation: str,
    searched: list[str],
) -> Finding:
    return Finding(
        title=title,
        category=category,
        kind=FindingKind.GAP,
        severity=severity,
        explanation=explanation,
        searched_for="Searched the report for: " + ", ".join(searched),
        detected_by=DetectedBy.RULE,
        rule_id=rule_id,
    )


def _weakness(
    rule_id: str,
    title: str,
    category: FindingCategory,
    severity: Severity,
    explanation: str,
    evidence: Evidence,
) -> Finding:
    return Finding(
        title=title,
        category=category,
        kind=FindingKind.WEAKNESS,
        severity=severity,
        explanation=explanation,
        evidence=[evidence],
        detected_by=DetectedBy.RULE,
        rule_id=rule_id,
    )


# --- evaluation -------------------------------------------------------------

VALIDATION_TERMS = [
    "cross validation", "cross-validation", "k-fold", "kfold", "stratified",
    "holdout", "hold-out", "validation set", "validation split",
]


@rule("no-evaluation-metrics")
def no_evaluation_metrics(ctx: RuleContext) -> Finding | None:
    if ctx.profile.evaluation.metrics:
        return None
    terms = ["accuracy", "precision", "recall", "f1", "auc", "rmse", "mae"]
    if ctx.mentions(*terms):
        return None
    return _gap(
        "no-evaluation-metrics",
        "No evaluation metrics are reported",
        FindingCategory.EVALUATION,
        Severity.HIGH,
        "Without a stated metric there is no way to tell whether the model "
        "works, or to compare it against anything. Any claim about "
        "performance in this report is currently unsupported.",
        terms,
    )


SPLIT_TERMS = [
    "train test split", "train/test split", "test split", "80/20", "70/30",
    "training and testing set",
]


@rule("no-validation-strategy")
def no_validation_strategy(ctx: RuleContext) -> Finding | None:
    if ctx.profile.evaluation.validation_strategy is not None:
        return None
    if ctx.mentions(*VALIDATION_TERMS):
        return None
    # A described-but-weak split is the single-split-only rule's job; this one
    # is only for a report that says nothing about validation at all.
    if ctx.mentions(*SPLIT_TERMS, affirmative_only=False):
        return None
    return _gap(
        "no-validation-strategy",
        "No validation strategy is described",
        FindingCategory.EVALUATION,
        Severity.HIGH,
        "The report does not say how the model was validated, so the reported "
        "results cannot be judged for overfitting. A single favourable split "
        "and a properly cross-validated result look identical from outside.",
        VALIDATION_TERMS,
    )


@rule("single-split-only")
def single_split_only(ctx: RuleContext) -> Finding | None:
    """A train/test split with no cross-validation anywhere."""
    if ctx.mentions(*VALIDATION_TERMS):
        return None
    quote = ctx.quote_for(*SPLIT_TERMS)
    if quote is None:
        return None
    return _weakness(
        "single-split-only",
        "Evaluated on a single train/test split",
        FindingCategory.EVALUATION,
        Severity.HIGH,
        "A single split makes the reported score dependent on which rows "
        "happened to land in the test set. With a small dataset the variance "
        "between splits can exceed the difference being claimed.",
        quote,
    )


@rule("accuracy-without-class-metrics")
def accuracy_without_class_metrics(ctx: RuleContext) -> Finding | None:
    metrics = ctx.metric_values()
    if "accuracy" not in metrics:
        return None
    if metrics & {"precision", "recall", "f1", "f1-score", "auc", "roc"}:
        return None
    quote = ctx.quote_for("accuracy")
    if quote is None:
        return None
    return _weakness(
        "accuracy-without-class-metrics",
        "Accuracy is reported without per-class metrics",
        FindingCategory.METRIC_SUITABILITY,
        Severity.MEDIUM,
        "Accuracy alone hides which classes the model fails on, and is "
        "misleading whenever the classes are not balanced. A model that never "
        "predicts a rare class can still post a high accuracy.",
        quote,
    )


@rule("no-baseline-comparison")
def no_baseline_comparison(ctx: RuleContext) -> Finding | None:
    if len(ctx.profile.algorithms) > 1:
        return None
    if ctx.mentions("baseline", "compared against", "comparison model"):
        return None
    return _gap(
        "no-baseline-comparison",
        "No baseline to compare against",
        FindingCategory.BASELINE,
        Severity.MEDIUM,
        "Only one approach appears in the report, so there is nothing to show "
        "the chosen method was the right one. A simple baseline is what turns "
        "a score into evidence that the complexity was worth it.",
        ["baseline", "comparison model", "a second algorithm"],
    )


# --- data -------------------------------------------------------------------


@rule("class-imbalance-unaddressed")
def class_imbalance_unaddressed(ctx: RuleContext) -> Finding | None:
    quote = ctx.quote_for("imbalance", "imbalanced", "skewed class")
    if quote is None:
        return None
    if ctx.mentions(
        "smote", "class weight", "class_weight", "resampl", "oversampl",
        "undersampl", "stratified",
    ):
        return None
    return _weakness(
        "class-imbalance-unaddressed",
        "Class imbalance is acknowledged but not addressed",
        FindingCategory.CLASS_IMBALANCE,
        Severity.HIGH,
        "The report notes imbalanced classes but describes no handling for "
        "it. Left untreated this biases the model toward the majority class "
        "and inflates any overall accuracy figure.",
        quote,
    )


@rule("resampling-before-split")
def resampling_before_split(ctx: RuleContext) -> Finding | None:
    """Resampling without saying it happened after the split leaks data."""
    quote = ctx.quote_for("smote", "oversampl", "undersampl", "resampl")
    if quote is None:
        return None
    if ctx.mentions(
        "after splitting", "after the split", "training set only",
        "training data only", "within each fold", "inside the fold",
        "only on the training",
    ):
        return None
    return _weakness(
        "resampling-before-split",
        "Resampling may have been applied before splitting",
        FindingCategory.DATA_LEAKAGE,
        Severity.HIGH,
        "The report describes resampling but does not say it was done after "
        "the train/test split. Resampling first copies or synthesises rows "
        "that then appear on both sides of the split, which inflates the test "
        "score. Worth confirming from the code before trusting the result.",
        quote,
    )


@rule("no-dataset-provenance")
def no_dataset_provenance(ctx: RuleContext) -> Finding | None:
    dataset = ctx.profile.dataset
    if dataset.name is not None or dataset.source is not None:
        return None
    if ctx.mentions("dataset", "corpus", "data set"):
        return None
    return _gap(
        "no-dataset-provenance",
        "The dataset is not identified",
        FindingCategory.REPRODUCIBILITY,
        Severity.MEDIUM,
        "Without naming the data or where it came from, nobody can reproduce "
        "the result or judge whether the data suits the problem.",
        ["dataset name", "data source", "corpus"],
    )


@rule("no-preprocessing-described")
def no_preprocessing_described(ctx: RuleContext) -> Finding | None:
    if ctx.profile.dataset.preprocessing:
        return None
    terms = [
        "normalis", "normaliz", "standardis", "standardiz", "scaling",
        "augmentation", "cleaning", "encoding", "tokenis", "tokeniz",
    ]
    if ctx.mentions(*terms):
        return None
    return _gap(
        "no-preprocessing-described",
        "No preprocessing is described",
        FindingCategory.FEATURE_ENGINEERING,
        Severity.LOW,
        "The report does not say how raw data became model input. That step "
        "usually affects results more than the choice of model, so leaving it "
        "out makes the work hard to reproduce or improve on.",
        terms,
    )


# --- engineering practice ---------------------------------------------------


@rule("no-explainability")
def no_explainability(ctx: RuleContext) -> Finding | None:
    terms = [
        "shap", "lime", "interpretab", "explainab", "feature importance",
        "saliency", "grad-cam", "attention map",
    ]
    if ctx.mentions(*terms):
        return None
    return _gap(
        "no-explainability",
        "No way to explain individual predictions",
        FindingCategory.EXPLAINABILITY,
        Severity.LOW,
        "Nothing in the report addresses why the model makes a given "
        "prediction. That is acceptable for a demonstration, but blocks use "
        "anywhere a decision has to be justified.",
        terms,
    )


@rule("no-testing")
def no_testing(ctx: RuleContext) -> Finding | None:
    terms = ["pytest", "unittest", "unit test", "test suite", "automated test"]
    if ctx.mentions(*terms):
        return None
    return _gap(
        "no-testing",
        "No automated tests are mentioned",
        FindingCategory.TESTING,
        Severity.MEDIUM,
        "Without tests, a change to preprocessing or training can silently "
        "alter results, and nobody finds out until the numbers are already in "
        "a report.",
        terms,
    )


@rule("no-deployment")
def no_deployment(ctx: RuleContext) -> Finding | None:
    terms = [
        "deploy", "docker", "flask", "fastapi", "streamlit", "heroku",
        "render", "vercel", "aws", "azure", "inference server", "rest api",
    ]
    if ctx.mentions(*terms):
        return None
    return _gap(
        "no-deployment",
        "No deployment or serving path",
        FindingCategory.DEPLOYMENT,
        Severity.MEDIUM,
        "The work stops at a trained model. Without a way to serve it, the "
        "result cannot be used or demonstrated outside the notebook it was "
        "built in.",
        terms,
    )


@rule("no-reproducibility-controls")
def no_reproducibility_controls(ctx: RuleContext) -> Finding | None:
    terms = ["random seed", "random_state", "set_seed", "reproducib", "deterministic"]
    if ctx.mentions(*terms):
        return None
    return _gap(
        "no-reproducibility-controls",
        "No random seed or reproducibility control",
        FindingCategory.REPRODUCIBILITY,
        Severity.LOW,
        "Training involves randomness in initialisation, shuffling and "
        "splitting. With no seed recorded, re-running the work gives a "
        "different number and the reported figure cannot be confirmed.",
        terms,
    )


@rule("unversioned-dependencies")
def unversioned_dependencies(ctx: RuleContext) -> Finding | None:
    """Report that currency cannot be judged -- never that a library is old.

    README section 4.3 only allows calling dependencies outdated when their
    versions can be established, so this fires on the *absence* of versions.
    """
    libraries = ctx.profile.stack.libraries + ctx.profile.stack.frameworks
    if not libraries:
        return None
    if re.search(r"\b\d+\.\d+(\.\d+)?\b", ctx._blob):
        return None
    names = ", ".join(c.value for c in libraries[:5])
    return _gap(
        "unversioned-dependencies",
        "Library versions are not recorded",
        FindingCategory.DEPENDENCIES,
        Severity.LOW,
        f"The report names libraries ({names}) without versions, so it is not "
        "possible to tell which releases were used, to reproduce the "
        "environment, or to assess whether any of them need updating. This is "
        "about the missing information, not about the libraries themselves.",
        ["version numbers", "requirements.txt", "environment file"],
    )


def run_rules(
    profile: ProjectProfile, document: ExtractedDocument
) -> list[Finding]:
    """Run every registered rule. A rule that raises is skipped, not fatal."""
    import logging

    logger = logging.getLogger(__name__)
    context = RuleContext(profile=profile, document=document)
    findings: list[Finding] = []

    for rule_id, fn in _RULES:
        try:
            result = fn(context)
        except Exception:  # one bad rule must not lose the others
            logger.exception("rule %s failed", rule_id)
            continue
        if result is not None:
            findings.append(result)

    return findings


def rule_ids() -> list[str]:
    return [rule_id for rule_id, _ in _RULES]
