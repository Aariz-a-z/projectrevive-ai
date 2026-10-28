"""Stage 2: weakness and gap analysis.

Two sources, merged. Deterministic rules run first and always produce
something, then the model is asked for what the rules cannot see -- issues
specific to this project's methodology rather than to a checklist. The rule
findings are shown to the model so it does not simply restate them.

Model findings go through the same citation verification as the profile. A
weakness whose quote cannot be found in the document it names is **dropped**,
not softened: an unsupported accusation about someone's report is worse than
no finding at all, and a weakness without a quote is exactly that.
"""

from __future__ import annotations

import logging

from app.analysis.rules import run_rules
from app.analysis.verify import verify_evidence
from app.llm.base import LLMProvider, StructuredResult, Usage
from app.llm.sanitize import prepare
from app.schemas.document import ExtractedDocument
from app.schemas.findings import (
    DetectedBy,
    Finding,
    FindingKind,
    FindingsReport,
    GapAnalysis,
)
from app.schemas.project import ProjectProfile

logger = logging.getLogger(__name__)

GAP_SYSTEM_PROMPT = """\
You are reviewing an AI/ML project report to identify weaknesses and gaps that \
affect whether its conclusions can be trusted.

You are given a structured summary of the project, a list of issues that \
automated rules already found, and the report itself.

Report only issues that are grounded in THIS report. For each one:

1. Choose a kind.
   - "weakness": something the report describes is problematic. You MUST quote \
the report text you object to, with the page number from the nearest preceding \
[page N] marker. Copy the quote exactly.
   - "gap": something expected is missing. An absence cannot be quoted, so \
instead fill "searched_for" with what you looked for.
2. Write "explanation" about THIS project specifically. Say what the \
consequence is for these results. Do not define the general concept.
3. Set "severity" by how much it undermines the project's own conclusions: \
"high" means the reported results may not mean what the report claims, \
"medium" limits usefulness or reproducibility, "low" is worth improving.

Rules you must follow:

- Never invent a quote or a page number. If you cannot quote it exactly, it is \
not a weakness.
- Do NOT call a technique, library or method outdated or inadequate merely \
because a newer alternative exists. An older method that fits the problem is a \
correct choice. Only object when something about THIS project makes it unsuitable.
- Do not repeat issues the automated rules already found. Add what they missed.
- If the report genuinely has few problems, return few findings. Do not pad.
- Put anything you could not assess into "notes".
"""


def _summarise_profile(profile: ProjectProfile) -> str:
    """A compact view of the project, so the model has structure to reason over."""

    def values(claims) -> str:
        return ", ".join(c.value for c in claims) or "none identified"

    lines = [
        "STRUCTURED SUMMARY (derived from the report by an earlier stage):",
        f"- Title: {profile.title.value}",
        f"- Domain: {profile.domain.value}",
        f"- Problem: {profile.problem_statement.value[:400]}",
        f"- Algorithms: {values(profile.algorithms)}",
        f"- Languages: {values(profile.stack.languages)}",
        f"- Libraries: {values(profile.stack.libraries)}",
        f"- Metrics: {values(profile.evaluation.metrics)}",
        f"- Validation: {profile.evaluation.validation_strategy.value if profile.evaluation.validation_strategy else 'not described'}",
        f"- Dataset: {profile.dataset.name.value if profile.dataset.name else 'not identified'}",
        f"- Stated limitations: {values(profile.stated_limitations) or 'none stated'}",
    ]
    return "\n".join(lines)


def _summarise_rules(findings: list[Finding]) -> str:
    if not findings:
        return "AUTOMATED RULES FOUND: nothing."
    lines = ["AUTOMATED RULES ALREADY FOUND (do not repeat these):"]
    lines += [f"- [{f.category.value}] {f.title}" for f in findings]
    return "\n".join(lines)


def _tokens(title: str) -> set[str]:
    return {w for w in title.lower().replace("-", " ").split() if len(w) > 3}


def _is_duplicate(candidate: Finding, existing: list[Finding]) -> bool:
    """Same category and a substantially overlapping title."""
    candidate_tokens = _tokens(candidate.title)
    if not candidate_tokens:
        return False
    for other in existing:
        if other.category is not candidate.category:
            continue
        other_tokens = _tokens(other.title)
        if not other_tokens:
            continue
        overlap = len(candidate_tokens & other_tokens)
        smaller = min(len(candidate_tokens), len(other_tokens))
        if smaller and overlap / smaller >= 0.5:
            return True
    return False


def _verify_model_findings(
    findings: list[Finding], document: ExtractedDocument
) -> tuple[list[Finding], list[str]]:
    kept: list[Finding] = []
    notes: list[str] = []

    for finding in findings:
        valid, problems = verify_evidence(finding.evidence, document)
        notes.extend(problems)

        if finding.kind is FindingKind.WEAKNESS and not valid:
            notes.append(
                f"Dropped the finding {finding.title!r}: it objected to "
                "something in the report but none of its citations could be "
                "verified against the document."
            )
            continue

        kept.append(
            finding.model_copy(update={"evidence": valid})
            if len(valid) != len(finding.evidence)
            else finding
        )

    return kept, notes


def analyse_gaps(
    profile: ProjectProfile,
    document: ExtractedDocument,
    provider: LLMProvider,
) -> StructuredResult[FindingsReport]:
    """Produce a merged, verified findings report."""
    rule_findings = run_rules(profile, document)
    logger.info("rules produced %d finding(s)", len(rule_findings))

    fenced, injection_warnings = prepare(document.to_prompt_text())
    user_content = "\n\n".join(
        [_summarise_profile(profile), _summarise_rules(rule_findings), fenced]
    )

    notes: list[str] = []
    warnings: list[str] = [*injection_warnings]
    model_findings: list[Finding] = []
    result: StructuredResult | None = None

    try:
        result = provider.structured(
            system=GAP_SYSTEM_PROMPT,
            document=user_content,
            schema=GapAnalysis,
            task="gap_analysis",
        )
    except Exception as exc:  # noqa: BLE001 - the rules must still be returned
        # A model failure degrades the analysis; it does not void it. The rule
        # findings are independent and still worth showing.
        logger.warning("gap analysis model stage failed: %s", exc)
        notes.append(
            "The model stage of the gap analysis failed, so only the "
            "automated rule findings are shown here."
        )
    else:
        verified, verify_notes = _verify_model_findings(
            result.parsed.findings, document
        )
        model_findings = verified
        notes.extend(verify_notes)
        notes.extend(result.parsed.notes)
        warnings.extend(result.warnings)

    merged = list(rule_findings)
    duplicates = 0
    for finding in model_findings:
        if _is_duplicate(finding, merged):
            duplicates += 1
            continue
        merged.append(finding)

    if duplicates:
        notes.append(
            f"{duplicates} model finding(s) restated something an automated "
            "rule had already found and were merged away."
        )

    merged.sort(key=lambda f: f.sort_key)
    report = FindingsReport(findings=merged, notes=notes)

    return StructuredResult(
        parsed=report,
        provider=result.provider if result else "rules-only",
        model=result.model if result else "deterministic-rules",
        usage=result.usage if result else Usage(),
        warnings=warnings,
    )
