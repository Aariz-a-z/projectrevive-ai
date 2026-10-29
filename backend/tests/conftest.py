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
from itertools import count
from pathlib import Path

import pytest

# The suite runs against SQLite by default. Setting TEST_DATABASE_URL points
# it at a real database instead, which is how CI exercises PostgreSQL.
#
# A separate variable rather than DATABASE_URL on purpose: the fixtures below
# drop every table before running, so reading the application's own setting
# here would mean an exported DATABASE_URL -- the one pointing at real data --
# silently became the thing this suite wipes.
_TMP_DB = Path(tempfile.gettempdir()) / "projectrevive_test.db"
_EXTERNAL_DB = os.environ.get("TEST_DATABASE_URL", "").strip()
USING_EXTERNAL_DB = bool(_EXTERNAL_DB)

os.environ["DATABASE_URL"] = _EXTERNAL_DB or f"sqlite:///{_TMP_DB.as_posix()}"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["ANTHROPIC_API_KEY"] = ""
# Fixed so tests never write the development .secret_key file.
os.environ["SECRET_KEY"] = "test-only-signing-key-not-used-outside-the-suite"

from fastapi.testclient import TestClient  # noqa: E402

from app.db.migrate import downgrade_to_base, upgrade_to_head  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import create_app  # noqa: E402
from app.ratelimit.deps import reset_all  # noqa: E402

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
    """Build the test database the way production does: with migrations.

    Using create_all here instead would mean the migration path is never
    exercised by the suite, and would also collide with the startup check,
    which migrates and would find tables it did not create.

    Against an external database the schema is torn down first. Several tests
    register fixed email addresses, and the unique index on them would make a
    second run fail with collisions rather than with anything meaningful.
    """
    url = os.environ["DATABASE_URL"]
    if USING_EXTERNAL_DB:
        downgrade_to_base(url)
    upgrade_to_head(url)

    yield

    engine.dispose()
    if not USING_EXTERNAL_DB:
        _TMP_DB.unlink(missing_ok=True)


@pytest.fixture(autouse=True)
def _reset_rate_limits() -> Iterator[None]:
    """Rate limiters are process-wide singletons.

    Without this every test would share one window, so the sixth test to call
    signup would start failing for reasons that have nothing to do with it.
    """
    reset_all()
    yield
    reset_all()


@pytest.fixture
def client() -> Iterator[TestClient]:
    """An anonymous client. Analysis endpoints reject it with 401."""
    with TestClient(create_app()) as test_client:
        yield test_client


# Counter so each test gets a distinct account in the shared test database.
_account_seq = count(1)

TEST_PASSWORD = "correct-horse-battery-staple"


def register(test_client: TestClient, email: str | None = None) -> str:
    """Sign up and leave the session cookie on the client. Returns the email."""
    address = email or f"user{next(_account_seq)}@example.com"
    response = test_client.post(
        "/api/auth/signup", json={"email": address, "password": TEST_PASSWORD}
    )
    assert response.status_code == 201, response.text
    return address


@pytest.fixture
def auth_client(client: TestClient) -> Iterator[TestClient]:
    """A client already signed in as a fresh account."""
    register(client)
    yield client


@pytest.fixture
def sample_pdf() -> bytes:
    return make_pdf(SAMPLE_PAGES)
