"""PDF text extraction via pdfplumber (MIT).

pdfplumber is used instead of PyMuPDF because PyMuPDF is AGPL-3.0, which would
force this whole project to be AGPL. pdfplumber also exposes per-word boxes,
which is what the page-level evidence references need.
"""

from __future__ import annotations

import logging
from io import BytesIO

import pdfplumber

from app.errors import EncryptedDocument, MalformedDocument
from app.schemas.document import PageText

logger = logging.getLogger(__name__)

# Below this many characters per page on average, a PDF is almost certainly
# scanned images rather than embedded text.
SCANNED_CHARS_PER_PAGE = 50


def extract_pdf(data: bytes) -> tuple[list[PageText], bool]:
    """Return (pages, looks_scanned).

    Raises EncryptedDocument or MalformedDocument rather than returning empty
    output, so the caller can tell the user what actually went wrong.
    """
    try:
        with pdfplumber.open(BytesIO(data)) as pdf:
            pages = [
                PageText(page_number=i, text=(page.extract_text() or ""))
                for i, page in enumerate(pdf.pages, start=1)
            ]
    except Exception as exc:  # pdfminer raises a wide variety of types here
        name = type(exc).__name__
        if "Password" in name or "password" in str(exc).lower():
            raise EncryptedDocument() from exc
        logger.warning("PDF parse failed: %s: %s", name, exc)
        raise MalformedDocument(detail=f"{name}: {exc}") from exc

    total_chars = sum(len(p.text.strip()) for p in pages)
    looks_scanned = bool(pages) and total_chars < SCANNED_CHARS_PER_PAGE * len(pages)
    return pages, looks_scanned


def page_count(data: bytes) -> int:
    """Cheap page count, so an over-long document is rejected before full parse."""
    try:
        with pdfplumber.open(BytesIO(data)) as pdf:
            return len(pdf.pages)
    except Exception as exc:
        name = type(exc).__name__
        if "Password" in name or "password" in str(exc).lower():
            raise EncryptedDocument() from exc
        raise MalformedDocument(detail=f"{name}: {exc}") from exc
