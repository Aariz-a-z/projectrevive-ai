"""Document extraction contract: raw text with page provenance."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PageText(BaseModel):
    """Text recovered from a single page, 1-indexed to match what a reader sees."""

    page_number: int = Field(ge=1)
    text: str

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


class ExtractedDocument(BaseModel):
    """The output of the document layer. Nothing here is AI-generated."""

    filename: str
    content_type: str
    page_count: int = Field(ge=0)
    pages: list[PageText]
    looks_scanned: bool = False

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages if not p.is_empty)

    @property
    def total_characters(self) -> int:
        return sum(len(p.text) for p in self.pages)

    def page_containing(self, needle: str) -> int | None:
        """Return the 1-indexed page a snippet appears on, for evidence refs."""
        probe = " ".join(needle.split()).lower()
        if not probe:
            return None
        for page in self.pages:
            if probe in " ".join(page.text.split()).lower():
                return page.page_number
        return None

    def to_prompt_text(self) -> str:
        """Render pages with explicit markers.

        Evidence references need page numbers, and an LLM can only cite a page
        it can see. Inlining `[page N]` markers is what makes `Evidence.page`
        verifiable rather than invented.
        """
        return "\n\n".join(
            f"[page {p.page_number}]\n{p.text.strip()}"
            for p in self.pages
            if not p.is_empty
        )
