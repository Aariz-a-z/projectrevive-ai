"""Shared test setup.

Environment is configured before `app` is imported anywhere, because the
database engine is created at import time. Fixtures generate real PDF and DOCX
bytes with reportlab/python-docx rather than committing binary files, so the
extraction tests exercise genuine parsers on genuine documents.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path

import pytest

_TMP_DB = Path(tempfile.gettempdir()) / "projectrevive_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB.as_posix()}"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["ANTHROPIC_API_KEY"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from app.db.session import engine, init_db  # noqa: E402
from app.main import create_app  # noqa: E402

SAMPLE_PAGES = [
    "Handwritten Digit Recognition Using Deep Learning",
    "1. Introduction. Recognising handwritten digits is a long standing problem "
    "in computer vision with applications in postal automation and cheque "
    "processing. This project builds a classifier for the MNIST dataset and "
    "evaluates how well it generalises to unseen samples collected by the "
    "authors. The work was carried out as a final year undergraduate project.",
    "2. Methodology. We implemented a CNN in Python using TensorFlow and Keras. "
    "Images were normalised and reshaped before training. We also trained an SVM "
    "and a random forest as comparison models using scikit-learn.",
    "3. Results. The CNN achieved an accuracy of 98.2 percent on the test split. "
    "We report precision and recall per class and include a confusion matrix.",
    "4. Limitations. A limitation of this work is that no cross validation was "
    "performed and the model was evaluated on a single train test split. Future "
    "work should address class imbalance in the authors own samples.",
]


def make_pdf(pages: list[str]) -> bytes:
    """Render text pages into a real PDF."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    for body in pages:
        y = height - 72
        for line in _wrap(body, 88):
            pdf.drawString(60, y, line)
            y -= 15
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def make_docx(paragraphs: list[str]) -> bytes:
    from docx import Document

    document = Document()
    for text in paragraphs:
        document.add_paragraph(text)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _wrap(text: str, width: int) -> list[str]:
    words, lines, current = text.split(), [], ""
    for word in words:
        if len(current) + len(word) + 1 > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return lines


@pytest.fixture(scope="session", autouse=True)
def _database() -> Iterator[None]:
    init_db()
    yield
    engine.dispose()
    _TMP_DB.unlink(missing_ok=True)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def sample_pdf() -> bytes:
    return make_pdf(SAMPLE_PAGES)
