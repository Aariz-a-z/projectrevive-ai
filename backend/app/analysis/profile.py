"""Stage 1 of analysis: extracted text -> validated ProjectProfile.

Two things happen here that matter more than the prompt:

- The document is fenced as untrusted data before it reaches a provider.
- Every evidence citation is checked against the document that was actually
  uploaded. A model that cites a page that does not exist, or quotes text that
  is not on that page, has its citation rejected and the claim demoted to an
  inference. README section 13 requires validating AI output before using it;
  an unverifiable citation is exactly the kind of thing that must not reach the
  user looking like a fact.
"""

from __future__ import annotations

from app.analysis.verify import verify_evidence
from app.llm.base import LLMProvider, StructuredResult
from app.llm.sanitize import prepare
from app.schemas.document import ExtractedDocument
from app.schemas.project import Claim, ClaimSource, ProjectProfile

PROFILE_SYSTEM_PROMPT = """\
You are analysing an academic or student AI/ML project report in order to build \
a structured representation of it.

The document is supplied with explicit page markers of the form [page N].

Rules you must follow:

1. For every field, decide whether the report actually says it.
   - If the report states it, set source to "stated" and cite at least one piece \
of evidence: the page number from the nearest preceding [page N] marker, and a \
short verbatim quote copied exactly from the document.
   - If you are inferring it, set source to "inferred" and explain your \
reasoning in the "reasoning" field. Do not attach fabricated evidence.
2. Never invent a page number or a quote. If you cannot quote it, it is an \
inference.
3. Do not describe a technique as outdated or inadequate here. This stage only \
records what the project is; judging it happens later.
4. If something is not determinable from the document, leave the field empty \
and add a short line to extraction_notes saying what was missing.
5. Quote text exactly as it appears, including any awkward phrasing. Quotes are \
shown to the user as evidence, so they must be checkable against the document.
"""


def _verify_claim(claim: Claim, document: ExtractedDocument) -> tuple[Claim, list[str]]:
    """Drop unverifiable citations; demote the claim if nothing survives."""
    valid, notes = verify_evidence(claim.evidence, document)

    if len(valid) == len(claim.evidence):
        return claim, notes

    if valid or claim.source is ClaimSource.INFERRED:
        return claim.model_copy(update={"evidence": valid}), notes

    # A "stated" claim with no surviving evidence cannot stay stated.
    demoted = claim.model_copy(
        update={
            "source": ClaimSource.INFERRED,
            "evidence": [],
            "reasoning": (
                (claim.reasoning or "")
                + " Reported as stated, but its citation could not be verified "
                "against the uploaded document, so it is shown as an inference."
            ).strip(),
        }
    )
    return demoted, notes


def _verify_profile(
    profile: ProjectProfile, document: ExtractedDocument
) -> tuple[ProjectProfile, list[str]]:
    """Walk the profile and verify every claim's citations."""
    all_notes: list[str] = []

    def fix(claim: Claim | None) -> Claim | None:
        if claim is None:
            return None
        checked, notes = _verify_claim(claim, document)
        all_notes.extend(notes)
        return checked

    def fix_list(claims: list[Claim]) -> list[Claim]:
        out = []
        for claim in claims:
            checked, notes = _verify_claim(claim, document)
            all_notes.extend(notes)
            out.append(checked)
        return out

    data = profile.model_copy(deep=True)
    data.title = fix(data.title)  # type: ignore[assignment]
    data.domain = fix(data.domain)  # type: ignore[assignment]
    data.problem_statement = fix(data.problem_statement)  # type: ignore[assignment]
    data.objectives = fix_list(data.objectives)
    data.intended_users = fix_list(data.intended_users)
    data.methodology = fix_list(data.methodology)
    data.algorithms = fix_list(data.algorithms)
    data.stated_limitations = fix_list(data.stated_limitations)
    data.stack.languages = fix_list(data.stack.languages)
    data.stack.frameworks = fix_list(data.stack.frameworks)
    data.stack.libraries = fix_list(data.stack.libraries)
    data.stack.tools = fix_list(data.stack.tools)
    data.dataset.name = fix(data.dataset.name)
    data.dataset.size = fix(data.dataset.size)
    data.dataset.source = fix(data.dataset.source)
    data.dataset.preprocessing = fix_list(data.dataset.preprocessing)
    data.evaluation.metrics = fix_list(data.evaluation.metrics)
    data.evaluation.reported_results = fix_list(data.evaluation.reported_results)
    data.evaluation.validation_strategy = fix(data.evaluation.validation_strategy)
    data.architecture_description = fix(data.architecture_description)

    if all_notes:
        data.extraction_notes = [*data.extraction_notes, *all_notes]

    return data, all_notes


def build_profile(
    document: ExtractedDocument, provider: LLMProvider
) -> StructuredResult[ProjectProfile]:
    """Produce a verified ProjectProfile for an uploaded document."""
    fenced, injection_warnings = prepare(document.to_prompt_text())

    result = provider.structured(
        system=PROFILE_SYSTEM_PROMPT,
        document=fenced,
        schema=ProjectProfile,
        task="project_profile",
    )

    verified, citation_notes = _verify_profile(result.parsed, document)
    result.parsed = verified
    result.warnings = [*result.warnings, *injection_warnings, *citation_notes]
    return result
