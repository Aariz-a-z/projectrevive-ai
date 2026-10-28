"""File type detection by content, not by extension.

README section 10 requires validating uploads "by content and allowed type",
so a .exe renamed to .pdf must be rejected here rather than downstream.
"""

from __future__ import annotations

import zipfile
from enum import Enum
from io import BytesIO

from app.errors import UnsupportedFileType

PDF_MAGIC = b"%PDF-"
ZIP_MAGIC = b"PK\x03\x04"


class DocumentKind(str, Enum):
    PDF = "pdf"
    DOCX = "docx"


def sniff(data: bytes) -> DocumentKind:
    """Identify an upload from its bytes, or raise UnsupportedFileType."""
    if data[:5] == PDF_MAGIC:
        return DocumentKind.PDF

    if data[:4] == ZIP_MAGIC:
        # Every OOXML file is a zip; a .docx specifically holds word/document.xml.
        # This also rejects .xlsx/.pptx, which are zips too.
        try:
            with zipfile.ZipFile(BytesIO(data)) as archive:
                names = set(archive.namelist())
        except zipfile.BadZipFile as exc:
            raise UnsupportedFileType(
                "That file looks like a zip archive but could not be opened."
            ) from exc
        if "word/document.xml" in names:
            return DocumentKind.DOCX
        raise UnsupportedFileType(
            "That looks like an Office file, but not a Word (.docx) document."
        )

    raise UnsupportedFileType()


MEDIA_TYPES = {
    DocumentKind.PDF: "application/pdf",
    DocumentKind.DOCX: (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ),
}
