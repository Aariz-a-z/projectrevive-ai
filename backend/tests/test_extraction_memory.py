"""Extraction memory stays bounded by batch size, not by page count.

This exists because of a defect that only appeared on a small host. An open
pdfplumber document retains every page it has parsed, and the char objects
behind one page cost roughly 10MB -- about two thousand times the text they
carry. Extracting in a single pass therefore cost:

    50 pages  ->   724MB
    250 pages ->  3383MB
    300 pages ->  4053MB

So a 367KB upload needed 4GB, and on a 512MB instance a 123KB upload was
enough to get the process OOM-killed mid-request. `MAX_PAGES` was 300 and had
never been validated against memory at all.

Reopening the document per batch bounds the peak by the batch size: the same
300-page document measured 152MB afterwards, for 4% more wall time. Neither
`Page.flush_cache()` nor `gc.collect()` fixes it alone, because the open
document still references the pages -- both were measured at 2401MB.

The mechanism is tested directly (the document really is reopened per batch,
and page numbers survive the boundaries) because that is deterministic
everywhere. The memory ceiling is asserted in a subprocess on POSIX only,
since peak RSS is a process-wide high-water mark and needs isolation to mean
anything.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap

import pytest

from app.config import Settings
from app.documents import pdf as pdf_backend
from app.documents.extract import extract
from tests.conftest import make_pdf

PAGES = pdf_backend.PAGE_BATCH * 3 + 2  # spans several batches, ends partway


def _many_pages(count: int) -> bytes:
    body = (
        "The model is a convolutional neural network trained on MNIST with an "
        "80/20 split. Accuracy was 98.2 percent. No cross validation was "
        "performed and no explainability analysis was carried out."
    )
    return make_pdf([f"Page {i} of the report. {body}" for i in range(1, count + 1)])


class TestBatching:
    def test_the_document_is_reopened_once_per_batch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Reopening is the whole fix; a single pass is the bug."""
        import pdfplumber

        real_open = pdfplumber.open
        calls: list[object] = []

        def counting_open(*args: object, **kwargs: object) -> object:
            calls.append(kwargs.get("pages"))
            return real_open(*args, **kwargs)

        monkeypatch.setattr(pdfplumber, "open", counting_open)

        data = _many_pages(PAGES)
        pages, _ = pdf_backend.extract_pdf(data)

        assert len(pages) == PAGES
        # One open to count the pages, then one per batch.
        batches = [c for c in calls if c is not None]
        expected = -(-PAGES // pdf_backend.PAGE_BATCH)  # ceiling division
        assert len(batches) == expected, (
            f"expected {expected} batched opens for {PAGES} pages at a batch "
            f"of {pdf_backend.PAGE_BATCH}, got {len(batches)}"
        )

    def test_page_numbers_survive_the_batch_boundaries(self) -> None:
        """Off-by-one here would misattribute every evidence citation."""
        pages, _ = pdf_backend.extract_pdf(_many_pages(PAGES))

        assert [p.page_number for p in pages] == list(range(1, PAGES + 1))

    def test_a_known_page_lands_on_its_own_number(self) -> None:
        """Stronger than a sequence check: the text must match the number.

        A batching bug that produced 1..N in order while shuffling the text
        would pass the test above.
        """
        pages, _ = pdf_backend.extract_pdf(_many_pages(PAGES))

        for page in pages:
            assert f"Page {page.page_number} of the report" in page.text

    def test_batching_does_not_change_what_is_extracted(self) -> None:
        """The batched result must equal a single-pass read of the same file."""
        import pdfplumber

        data = _many_pages(PAGES)
        with pdfplumber.open(__import__("io").BytesIO(data)) as doc:
            single_pass = [p.extract_text() or "" for p in doc.pages]

        pages, _ = pdf_backend.extract_pdf(data)

        assert [p.text for p in pages] == single_pass

    def test_a_caller_supplied_count_is_trusted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """extract() passes the count it already has, saving a second parse."""
        calls = 0
        real_count = pdf_backend.page_count

        def counting(data: bytes) -> int:
            nonlocal calls
            calls += 1
            return real_count(data)

        monkeypatch.setattr(pdf_backend, "page_count", counting)
        extract(_many_pages(4), "r.pdf", Settings(llm_provider="mock"))

        assert calls == 1, "the page count should be taken once, not twice"


@pytest.mark.skipif(
    not sys.platform.startswith("linux"),
    reason="peak RSS via resource.getrusage is POSIX-only; CI runs Linux",
)
class TestMemoryCeiling:
    def test_a_long_document_stays_well_under_a_small_instance(self) -> None:
        """The regression this file exists for, measured rather than argued.

        Runs in a subprocess because ru_maxrss is a process-wide high-water
        mark: by the time pytest reaches this test, the suite has already
        allocated enough to make an in-process reading meaningless.

        The ceiling is 600MB against a measured ~152MB. Deliberately loose --
        this is here to catch a return to gigabytes, not to pin an exact
        number that would make the test fail on an unrelated allocation.
        """
        script = textwrap.dedent(
            """
            import resource, sys
            sys.path.insert(0, ".")
            from tests.conftest import make_pdf
            from app.documents.pdf import extract_pdf

            body = ("The model is a convolutional neural network trained on "
                    "MNIST with an 80/20 split. Accuracy was 98.2 percent. "
                    "No cross validation was performed.")
            data = make_pdf([f"Page {i}. {body}" for i in range(1, 121)])
            pages, _ = extract_pdf(data)
            assert len(pages) == 120, len(pages)
            print(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
            """
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=600,
        )
        assert result.returncode == 0, result.stderr[-2000:]

        peak_mib = int(result.stdout.strip().splitlines()[-1]) / 1024
        assert peak_mib < 600, (
            f"extracting 120 pages peaked at {peak_mib:.0f}MiB. Before "
            "batching, 50 pages alone cost 724MiB and a 512MB host was "
            "OOM-killed; this is that defect returning."
        )
