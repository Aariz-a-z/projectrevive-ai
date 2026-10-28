"""Document layer: type detection, extraction, and the failure paths."""

from __future__ import annotations

import pytest

from app.config import Settings
from app.documents.detect import DocumentKind, sniff
from app.documents.extract import extract
from app.errors import (
    EmptyDocument,
    FileTooLarge,
    MalformedDocument,
    ScannedDocument,
    UnsupportedFileType,
)
from tests.conftest import SAMPLE_PAGES, make_docx, make_pdf


@pytest.fixture
def settings() -> Settings:
    return Settings(llm_provider="mock", max_upload_mb=5, max_pages=50)


class TestDetection:
    def test_detects_pdf(self, sample_pdf: bytes) -> None:
        assert sniff(sample_pdf) is DocumentKind.PDF

    def test_detects_docx(self) -> None:
        assert sniff(make_docx(["hello"])) is DocumentKind.DOCX

    def test_rejects_executable_renamed_as_pdf(self) -> None:
        with pytest.raises(UnsupportedFileType):
            sniff(b"MZ\x90\x00\x03\x00\x00\x00 this is a windows binary")

    def test_rejects_plain_text(self) -> None:
        with pytest.raises(UnsupportedFileType):
            sniff(b"just some text, not a document")

    def test_rejects_non_docx_zip(self) -> None:
        import zipfile
        from io import BytesIO

        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("notes.txt", "hi")
        with pytest.raises(UnsupportedFileType):
            sniff(buffer.getvalue())


class TestExtraction:
    def test_extracts_pdf_with_page_numbers(
        self, sample_pdf: bytes, settings: Settings
    ) -> None:
        document = extract(sample_pdf, "report.pdf", settings)
        assert document.page_count == len(SAMPLE_PAGES)
        assert "CNN" in document.full_text
        # Methodology is on page 3 of the fixture; page refs must be accurate.
        assert document.page_containing("TensorFlow and Keras") == 3

    def test_page_markers_are_rendered_for_the_model(
        self, sample_pdf: bytes, settings: Settings
    ) -> None:
        text = extract(sample_pdf, "report.pdf", settings).to_prompt_text()
        assert "[page 1]" in text and "[page 5]" in text

    def test_extracts_docx(self, settings: Settings) -> None:
        data = make_docx(["Project title", "We used a CNN with Keras." * 20])
        document = extract(data, "report.docx", settings)
        assert "CNN" in document.full_text

    def test_rejects_empty_file(self, settings: Settings) -> None:
        with pytest.raises(EmptyDocument):
            extract(b"", "empty.pdf", settings)

    def test_rejects_oversized_file(self, settings: Settings) -> None:
        with pytest.raises(FileTooLarge):
            extract(b"%PDF-" + b"0" * (6 * 1024 * 1024), "big.pdf", settings)

    def test_rejects_truncated_pdf(self, settings: Settings) -> None:
        with pytest.raises(MalformedDocument):
            extract(b"%PDF-1.7\nbroken garbage never terminated", "bad.pdf", settings)

    def test_rejects_scanned_pdf_when_ocr_disabled(self, settings: Settings) -> None:
        """A PDF with pages but effectively no text reads as scanned."""
        blank = make_pdf(["", "", ""])
        with pytest.raises(ScannedDocument):
            extract(blank, "scan.pdf", settings)

    def test_rejects_document_over_page_budget(self) -> None:
        from app.errors import DocumentTooLong

        tight = Settings(llm_provider="mock", max_pages=2)
        with pytest.raises(DocumentTooLong):
            extract(make_pdf(["a", "b", "c"]), "long.pdf", tight)
