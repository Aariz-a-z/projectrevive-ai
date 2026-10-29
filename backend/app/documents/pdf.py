"""PDF text extraction via pdfplumber (MIT).

pdfplumber is used instead of PyMuPDF because PyMuPDF is AGPL-3.0, which would
force this whole project to be AGPL. pdfplumber also exposes per-word boxes,
which is what the page-level evidence references need.

Memory is the delicate part here, so the extraction loop is deliberate rather
than the obvious comprehension. See `PAGE_BATCH`.
"""

from __future__ import annotations

import gc
import logging
from io import BytesIO

import pdfplumber

from app.errors import EncryptedDocument, MalformedDocument
from app.schemas.document import PageText

logger = logging.getLogger(__name__)

# Below this many characters per page on average, a PDF is almost certainly
# scanned images rather than embedded text.
SCANNED_CHARS_PER_PAGE = 50

# How many pages to hold open at once.
#
# An open pdfplumber document keeps every page it has parsed, and the char
# objects behind one page of text cost roughly 10MB -- about two thousand
# times the text they carry. Extracting a 300-page document in one pass
# therefore peaked at 4GB, which on a 512MB host meant a 367KB upload killed
# the process. Neither `Page.flush_cache()` nor `gc.collect()` helps while the
# document is open, because the document itself still references the pages;
# only closing it releases them.
#
# So the document is reopened per batch, which bounds peak memory by the batch
# size instead of the page count. Measured on a 300-page document: 4053MB in
# one pass, 135MB at a batch of 10, for 4% more wall time. 10 keeps the
# extraction peak near 100MB, which leaves room on a 512MB instance.
PAGE_BATCH = 10


def _document_error(exc: Exception) -> Exception:
    """Map a parse failure onto the error the user should see."""
    name = type(exc).__name__
    if "Password" in name or "password" in str(exc).lower():
        return EncryptedDocument()
    logger.warning("PDF parse failed: %s: %s", name, exc)
    return MalformedDocument(detail=f"{name}: {exc}")


def extract_pdf(data: bytes, total: int | None = None) -> tuple[list[PageText], bool]:
    """Return (pages, looks_scanned).

    Raises EncryptedDocument or MalformedDocument rather than returning empty
    output, so the caller can tell the user what actually went wrong.

    `total` lets a caller that has already counted the pages -- the page-budget
    check does -- avoid paying for a second count.
    """
    if total is None:
        total = page_count(data)

    # Only worth collecting between batches, and only when there is more than
    # one. A full collection costs real time, and the common upload is a
    # handful of pages that fits in a single batch.
    collect_between_batches = total > PAGE_BATCH

    pages: list[PageText] = []
    for start in range(0, total, PAGE_BATCH):
        wanted = list(range(start + 1, min(start + PAGE_BATCH, total) + 1))
        try:
            with pdfplumber.open(BytesIO(data), pages=wanted) as pdf:
                for page in pdf.pages:
                    pages.append(
                        PageText(
                            page_number=page.page_number,
                            text=(page.extract_text() or ""),
                        )
                    )
                    page.flush_cache()
        except Exception as exc:  # pdfminer raises a wide variety of types
            raise _document_error(exc) from exc

        # pdfminer leaves reference cycles behind, so the memory the closed
        # document held is garbage rather than freed until this runs.
        if collect_between_batches:
            gc.collect()

    total_chars = sum(len(p.text.strip()) for p in pages)
    looks_scanned = bool(pages) and total_chars < SCANNED_CHARS_PER_PAGE * len(pages)
    return pages, looks_scanned


def page_count(data: bytes) -> int:
    """Cheap page count, so an over-long document is rejected before full parse.

    Cheap because building the page list parses the page tree but extracts no
    text; the expensive char objects are only created on demand.
    """
    try:
        with pdfplumber.open(BytesIO(data)) as pdf:
            return len(pdf.pages)
    except Exception as exc:
        raise _document_error(exc) from exc
