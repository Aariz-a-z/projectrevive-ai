"""Entry point for the document layer: bytes in, ExtractedDocument out."""

from __future__ import annotations

from app.config import Settings
from app.documents import pdf as pdf_backend
from app.documents.detect import MEDIA_TYPES, DocumentKind, sniff
from app.documents.docx import extract_docx
from app.errors import (
    DocumentTooLong,
    EmptyDocument,
    FileTooLarge,
    ScannedDocument,
)
from app.schemas.document import ExtractedDocument


def extract(data: bytes, filename: str, settings: Settings) -> ExtractedDocument:
    """Validate and extract an upload.

    Order matters: size, then type, then page budget, then text. Each check
    raises a specific error so the user gets an actionable message.
    """
    if len(data) > settings.max_upload_bytes:
        raise FileTooLarge(
            f"That file is {len(data) / 1_048_576:.1f} MB, over the "
            f"{settings.max_upload_mb} MB limit."
        )
    if not data:
        raise EmptyDocument("That file is empty.")

    kind = sniff(data)
    looks_scanned = False

    if kind is DocumentKind.PDF:
        pages_total = pdf_backend.page_count(data)
        if pages_total > settings.max_pages:
            raise DocumentTooLong(
                f"That document has {pages_total} pages, over the "
                f"{settings.max_pages} page limit."
            )
        pages, looks_scanned = pdf_backend.extract_pdf(data)
    else:
        pages = extract_docx(data)

    document = ExtractedDocument(
        filename=filename,
        content_type=MEDIA_TYPES[kind],
        page_count=len(pages),
        pages=pages,
        looks_scanned=looks_scanned,
    )

    if looks_scanned and not settings.enable_ocr:
        raise ScannedDocument()
    if not document.full_text.strip():
        raise EmptyDocument()

    return document
