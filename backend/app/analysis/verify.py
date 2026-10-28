"""Checking citations against the document they claim to come from.

Shared by the profile and gap stages. A model can produce a page number and a
quote that look entirely plausible and correspond to nothing; this is the only
thing standing between that and a user who believes it. Keeping one
implementation means the rule cannot be enforced in one stage and quietly
skipped in another.
"""

from __future__ import annotations

from app.schemas.document import ExtractedDocument
from app.schemas.project import Evidence


def _normalise(text: str) -> str:
    return " ".join(text.split()).lower()


def verify_evidence(
    evidence: list[Evidence], document: ExtractedDocument
) -> tuple[list[Evidence], list[str]]:
    """Return (citations that check out, notes about the ones that did not).

    A citation survives only if its page exists and its quote actually appears
    on that page. Whitespace is normalised before comparison, because a PDF
    extractor and a model will not agree on line breaks; nothing else is
    loosened, so a paraphrase is treated as a failed citation rather than a
    near-enough match.
    """
    valid: list[Evidence] = []
    notes: list[str] = []

    for item in evidence:
        if item.page < 1 or item.page > document.page_count:
            notes.append(
                f"Discarded a citation to page {item.page}, which does not "
                f"exist in a {document.page_count}-page document."
            )
            continue

        page_text = _normalise(document.pages[item.page - 1].text)
        quote = _normalise(item.quote)
        if quote and quote not in page_text:
            notes.append(
                f"Discarded a quote attributed to page {item.page} that does "
                f"not appear on that page: {item.quote[:60]!r}"
            )
            continue

        valid.append(item)

    return valid, notes
