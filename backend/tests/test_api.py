"""HTTP surface: upload, retrieval, and error responses."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import SAMPLE_PAGES, make_docx, make_pdf


def _upload(client: TestClient, data: bytes, name: str, mime: str = "application/pdf"):
    return client.post("/api/analyses", files={"file": (name, data, mime)})


class TestHealth:
    def test_reports_mock_provider_honestly(self, client: TestClient) -> None:
        body = client.get("/api/health").json()
        assert body["status"] == "ok"
        assert body["llm"]["is_mock"] is True
        assert body["llm"]["api_key_configured"] is False


class TestUpload:
    def test_accepts_a_pdf_and_returns_a_profile(
        self, client: TestClient, sample_pdf: bytes
    ) -> None:
        response = _upload(client, sample_pdf, "report.pdf")
        assert response.status_code == 201, response.text

        body = response.json()
        assert body["page_count"] == len(SAMPLE_PAGES)
        assert body["provenance"]["is_mock"] is True
        assert body["title"]
        assert body["claim_counts"]["total"] > 0
        assert body["claim_counts"]["stated"] > 0
        assert body["profile"]["algorithms"]

    def test_accepts_a_docx(self, client: TestClient) -> None:
        data = make_docx(["Sentiment Analysis Project", "We used BERT. " * 40])
        response = _upload(
            client,
            data,
            "report.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        assert response.status_code == 201, response.text

    def test_round_trips_through_storage(
        self, client: TestClient, sample_pdf: bytes
    ) -> None:
        created = _upload(client, sample_pdf, "report.pdf").json()
        fetched = client.get(f"/api/analyses/{created['id']}")

        assert fetched.status_code == 200
        assert fetched.json()["profile"] == created["profile"]

    def test_appears_in_the_listing(
        self, client: TestClient, sample_pdf: bytes
    ) -> None:
        created = _upload(client, sample_pdf, "listed.pdf").json()
        ids = [row["id"] for row in client.get("/api/analyses").json()]
        assert created["id"] in ids


class TestUploadErrors:
    def test_rejects_an_executable_renamed_as_pdf(self, client: TestClient) -> None:
        response = _upload(client, b"MZ\x90\x00 binary payload", "malware.pdf")
        assert response.status_code == 415
        assert response.json()["code"] == "unsupported_file_type"

    def test_rejects_an_empty_file(self, client: TestClient) -> None:
        response = _upload(client, b"", "empty.pdf")
        assert response.status_code == 422
        assert response.json()["code"] == "empty_document"

    def test_rejects_a_scanned_pdf_with_a_clear_message(
        self, client: TestClient
    ) -> None:
        response = _upload(client, make_pdf(["", "", ""]), "scan.pdf")
        assert response.status_code == 422
        body = response.json()
        assert body["code"] == "scanned_document"
        assert "ocr" in body["message"].lower()

    def test_rejects_a_malformed_pdf(self, client: TestClient) -> None:
        response = _upload(client, b"%PDF-1.4 truncated nonsense", "bad.pdf")
        assert response.status_code == 422
        assert response.json()["code"] == "malformed_document"

    def test_unknown_analysis_id_is_404(self, client: TestClient) -> None:
        response = client.get("/api/analyses/does-not-exist")
        assert response.status_code == 404
        assert response.json()["code"] == "analysis_not_found"


class TestMissingCredentials:
    def test_anthropic_without_a_key_fails_with_a_clear_message(self) -> None:
        """README section 8 requires the missing-credentials path to be tested."""
        from app.config import Settings
        from app.errors import LLMUnavailable
        from app.llm.registry import get_provider

        try:
            get_provider(Settings(llm_provider="anthropic", anthropic_api_key=None))
        except LLMUnavailable as exc:
            assert "ANTHROPIC_API_KEY" in exc.message
        else:
            raise AssertionError("expected LLMUnavailable")
