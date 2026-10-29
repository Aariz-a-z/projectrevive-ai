"""The development roadmap and the exportable report."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from app.analysis.gaps import analyse_gaps
from app.analysis.profile import build_profile
from app.config import Settings
from app.documents.extract import extract
from app.llm.mock_provider import MockProvider
from app.recommend.engine import recommend
from app.roadmap.builder import build_roadmap
from app.schemas.roadmap import PHASE_ORDER, PhaseId
from tests.conftest import SAMPLE_PAGES, make_pdf, register

SETTINGS = Settings(llm_provider="mock")


def _recommendations():
    document = extract(make_pdf(SAMPLE_PAGES), "r.pdf", SETTINGS)
    profile = build_profile(document, MockProvider()).parsed
    findings = analyse_gaps(profile, document, MockProvider()).parsed.findings
    return recommend(profile, findings, document).recommendations


class TestRoadmapOrdering:
    def test_phases_follow_the_declared_order(self) -> None:
        roadmap = build_roadmap(_recommendations())
        ids = [phase.id for phase in roadmap.phases]
        assert ids == [p for p in PHASE_ORDER if p in ids]

    def test_order_numbers_are_sequential(self) -> None:
        roadmap = build_roadmap(_recommendations())
        assert [p.order for p in roadmap.phases] == list(
            range(1, len(roadmap.phases) + 1)
        )

    def test_evaluation_work_comes_before_shipping(self) -> None:
        """The reason the ordering exists: later work is measured by this."""
        roadmap = build_roadmap(_recommendations())
        by_id = {phase.id: phase.order for phase in roadmap.phases}

        assert PhaseId.TRUSTWORTHY in by_id
        if PhaseId.SHIP in by_id:
            assert by_id[PhaseId.TRUSTWORTHY] < by_id[PhaseId.SHIP]

    def test_cross_validation_lands_in_the_first_phase(self) -> None:
        roadmap = build_roadmap(_recommendations())
        first = roadmap.phases[0]
        assert first.id is PhaseId.TRUSTWORTHY
        assert any("cross-validation" in t.title for t in first.tasks)

    def test_every_phase_explains_why_it_is_there(self) -> None:
        for phase in build_roadmap(_recommendations()).phases:
            assert len(phase.rationale) > 40

    def test_empty_phases_are_omitted(self) -> None:
        for phase in build_roadmap(_recommendations()).phases:
            assert phase.tasks


class TestRoadmapContent:
    def test_every_task_traces_to_a_recommendation(self) -> None:
        recommendations = _recommendations()
        known = {r.id for r in recommendations}
        roadmap = build_roadmap(recommendations)

        assert roadmap.task_count == len(recommendations)
        for phase in roadmap.phases:
            for task in phase.tasks:
                assert task.recommendation_id in known

    def test_every_task_says_how_to_tell_it_worked(self) -> None:
        for phase in build_roadmap(_recommendations()).phases:
            for task in phase.tasks:
                assert len(task.validation) > 10

    def test_ranking_within_a_phase_is_preserved(self) -> None:
        """Re-sorting here would apply a second, undocumented priority."""
        recommendations = _recommendations()
        order = [r.id for r in recommendations]
        for phase in build_roadmap(recommendations).phases:
            ids = [t.recommendation_id for t in phase.tasks]
            assert ids == sorted(ids, key=order.index)

    def test_no_time_estimates_are_invented(self) -> None:
        """Section 8 forbids fabricated figures; a duration here would be one."""
        roadmap = build_roadmap(_recommendations())
        blob = roadmap.model_dump_json().lower()
        for unit in ("hours", "days", "weeks", "sprint", "man-day"):
            assert f" {unit}" not in blob.replace("no time estimates", "")

    def test_it_says_why_there_are_no_time_estimates(self) -> None:
        notes = " ".join(build_roadmap(_recommendations()).notes).lower()
        assert "no time estimates" in notes

    def test_complexity_mix_totals_the_tasks(self) -> None:
        roadmap = build_roadmap(_recommendations())
        assert sum(roadmap.complexity_mix().values()) == roadmap.task_count

    def test_no_recommendations_produces_an_empty_plan(self) -> None:
        roadmap = build_roadmap([])
        assert roadmap.phases == []
        assert any("no plan" in n.lower() for n in roadmap.notes)


class TestReportExport:
    def _analysis(self, client: TestClient) -> dict:
        return client.post(
            "/api/analyses",
            files={"file": ("r.pdf", make_pdf(SAMPLE_PAGES), "application/pdf")},
        ).json()

    def test_downloads_as_markdown_with_a_filename(
        self, auth_client: TestClient
    ) -> None:
        analysis = self._analysis(auth_client)
        response = auth_client.get(f"/api/analyses/{analysis['id']}/report.md")

        assert response.status_code == 200
        assert "text/markdown" in response.headers["content-type"]
        assert "attachment" in response.headers["content-disposition"]
        assert ".md" in response.headers["content-disposition"]

    def test_contains_all_nine_sections(self, auth_client: TestClient) -> None:
        analysis = self._analysis(auth_client)
        body = auth_client.get(f"/api/analyses/{analysis['id']}/report.md").text

        headings = re.findall(r"^## (\d)\. ", body, re.M)
        assert headings == [str(n) for n in range(1, 10)]

    def test_states_what_has_not_been_measured(
        self, auth_client: TestClient
    ) -> None:
        """The section that stops the rest reading as more authoritative."""
        analysis = self._analysis(auth_client)
        body = auth_client.get(f"/api/analyses/{analysis['id']}/report.md").text

        assert "has not been measured" in body
        assert "no interaction data" in body.lower()
        assert "Assumptions made about your project" in body

    def test_declares_when_no_model_was_used(
        self, auth_client: TestClient
    ) -> None:
        analysis = self._analysis(auth_client)
        body = auth_client.get(f"/api/analyses/{analysis['id']}/report.md").text
        assert "No language model was used" in body

    def test_includes_the_architecture_diagrams(
        self, auth_client: TestClient
    ) -> None:
        analysis = self._analysis(auth_client)
        body = auth_client.get(f"/api/analyses/{analysis['id']}/report.md").text

        assert body.count("```mermaid") == 2
        assert "flowchart TD" in body

    def test_quotes_carry_their_page(self, auth_client: TestClient) -> None:
        analysis = self._analysis(auth_client)
        body = auth_client.get(f"/api/analyses/{analysis['id']}/report.md").text
        assert re.search(r"” — p\d+", body)

    def test_recommendations_state_their_trade_offs(
        self, auth_client: TestClient
    ) -> None:
        analysis = self._analysis(auth_client)
        body = auth_client.get(f"/api/analyses/{analysis['id']}/report.md").text
        assert "**Trade-offs.**" in body

    def test_another_account_cannot_download_it(
        self, client: TestClient
    ) -> None:
        register(client, "report-owner@example.com")
        analysis = self._analysis(client)

        client.post("/api/auth/logout")
        register(client, "report-intruder@example.com")

        response = client.get(f"/api/analyses/{analysis['id']}/report.md")
        assert response.status_code == 404

    def test_requires_a_session(self, client: TestClient) -> None:
        assert client.get("/api/analyses/whatever/report.md").status_code == 401


class TestRoadmapInTheApi:
    def test_analysis_detail_carries_the_roadmap(
        self, auth_client: TestClient
    ) -> None:
        created = auth_client.post(
            "/api/analyses",
            files={"file": ("r.pdf", make_pdf(SAMPLE_PAGES), "application/pdf")},
        ).json()

        assert created["roadmap"]["phases"]
        assert created["roadmap"]["phases"][0]["order"] == 1


class TestReportPolish:
    def test_warnings_are_not_repeated(self, auth_client: TestClient) -> None:
        """Both pipeline stages raise the same provider-level caveat."""
        created = auth_client.post(
            "/api/analyses",
            files={"file": ("r.pdf", make_pdf(SAMPLE_PAGES), "application/pdf")},
        ).json()

        warnings = created["warnings"]
        assert len(warnings) == len(set(warnings))

    def test_singular_counts_read_correctly(
        self, auth_client: TestClient
    ) -> None:
        created = auth_client.post(
            "/api/analyses",
            files={"file": ("r.pdf", make_pdf(SAMPLE_PAGES), "application/pdf")},
        ).json()
        body = auth_client.get(f"/api/analyses/{created['id']}/report.md").text

        assert " 1 are inferred" not in body
        assert " 1 are stated" not in body
