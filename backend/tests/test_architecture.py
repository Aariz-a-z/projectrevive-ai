"""Component graphs and Mermaid rendering."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.analysis.gaps import analyse_gaps
from app.analysis.profile import build_profile
from app.architecture.graph import build_current, build_proposed, build_view
from app.architecture.mermaid import MermaidError, escape_label, render, validate
from app.config import Settings
from app.documents.extract import extract
from app.llm.mock_provider import MockProvider
from app.recommend.engine import recommend
from app.schemas.architecture import (
    ComponentGraph,
    Edge,
    Node,
    NodeKind,
    Origin,
)
from tests.conftest import SAMPLE_PAGES, make_pdf

SETTINGS = Settings(llm_provider="mock")


def _context():
    document = extract(make_pdf(SAMPLE_PAGES), "r.pdf", SETTINGS)
    profile = build_profile(document, MockProvider()).parsed
    findings = analyse_gaps(profile, document, MockProvider()).parsed.findings
    recommendations = recommend(profile, findings, document).recommendations
    return profile, recommendations


def _node(node_id: str, kind: NodeKind = NodeKind.MODEL, label: str = "X") -> Node:
    return Node(id=node_id, label=label, kind=kind, origin=Origin.REPORT)


class TestGraphValidation:
    def test_rejects_an_edge_to_a_node_that_does_not_exist(self) -> None:
        """A dangling edge renders as a phantom box or fails to parse."""
        with pytest.raises(ValidationError, match="unknown node"):
            ComponentGraph(
                title="t",
                nodes=[_node("A")],
                edges=[Edge(source="A", target="Ghost")],
            )

    def test_rejects_duplicate_node_ids(self) -> None:
        with pytest.raises(ValidationError, match="duplicate node ids"):
            ComponentGraph(title="t", nodes=[_node("A"), _node("A")])

    def test_rejects_a_node_id_that_is_not_a_bare_identifier(self) -> None:
        """An id with punctuation changes the meaning of the rendered line."""
        with pytest.raises(ValidationError, match="bare identifier"):
            _node("my node")

    def test_accepts_a_coherent_graph(self) -> None:
        graph = ComponentGraph(
            title="t",
            nodes=[_node("A"), _node("B")],
            edges=[Edge(source="A", target="B")],
        )
        assert len(graph.edges) == 1


class TestLabelEscaping:
    @pytest.mark.parametrize(
        "raw",
        [
            'MNIST "handwritten"',
            "MNIST [v2]",
            "Dataset (cleaned)",
            "a|b",
            "line\nbreak",
            "<script>",
            "semi;colon",
        ],
    )
    def test_dangerous_characters_do_not_survive(self, raw: str) -> None:
        escaped = escape_label(raw)
        for char in '"[]{}|<>\n;':
            assert char not in escaped

    def test_empty_label_becomes_something_renderable(self) -> None:
        assert escape_label("   ") == "unnamed"

    def test_a_real_label_survives_readably(self) -> None:
        assert escape_label("  CNN,  random forest ") == "CNN, random forest"

    def test_a_hostile_label_still_renders_a_valid_diagram(self) -> None:
        """This is the case that would silently corrupt a diagram."""
        graph = ComponentGraph(
            title="t",
            nodes=[_node("A", label='Set [x] "y" | z')],
        )
        validate(render(graph), graph)


class TestMermaidValidation:
    def test_rejects_text_without_a_flowchart_header(self) -> None:
        with pytest.raises(MermaidError, match="flowchart"):
            validate("A --> B")

    def test_rejects_an_edge_to_an_undeclared_node(self) -> None:
        with pytest.raises(MermaidError, match="undeclared"):
            validate('flowchart TD\n    A["a"]\n    A --> B')

    def test_rejects_unbalanced_quotes(self) -> None:
        with pytest.raises(MermaidError, match="unbalanced quotes"):
            validate('flowchart TD\n    A["a]')

    def test_rejects_a_line_it_does_not_understand(self) -> None:
        with pytest.raises(MermaidError, match="unrecognised line"):
            validate("flowchart TD\n    this is not mermaid")

    def test_accepts_what_the_renderer_produces(self) -> None:
        graph = ComponentGraph(
            title="t",
            nodes=[_node("A"), _node("B", kind=NodeKind.DATA)],
            edges=[Edge(source="B", target="A", label="feeds")],
        )
        validate(render(graph), graph)

    def test_notices_when_rendered_nodes_do_not_match_the_graph(self) -> None:
        graph = ComponentGraph(title="t", nodes=[_node("A")])
        with pytest.raises(MermaidError, match="do not match the graph"):
            validate('flowchart TD\n    Z["z"]', graph)


class TestCurrentGraph:
    def test_contains_only_what_the_report_evidences(self) -> None:
        profile, _ = _context()
        graph = build_current(profile)

        assert graph.nodes
        assert all(n.origin is Origin.REPORT for n in graph.nodes)
        # The sample report describes no serving or monitoring, so neither
        # should be invented to make the picture look complete.
        assert not graph.of_kind(NodeKind.SERVING)
        assert not graph.of_kind(NodeKind.MONITORING)

    def test_includes_the_models_the_report_names(self) -> None:
        profile, _ = _context()
        model_nodes = build_current(profile).of_kind(NodeKind.MODEL)
        assert model_nodes
        assert "CNN" in model_nodes[0].label

    def test_omits_evaluation_when_no_metrics_were_found(self) -> None:
        document = extract(make_pdf(["T", "We built a thing. " * 30]), "r.pdf", SETTINGS)
        profile = build_profile(document, MockProvider()).parsed
        assert not build_current(profile).of_kind(NodeKind.EVALUATION)

    def test_edges_follow_the_pipeline_order(self) -> None:
        profile, _ = _context()
        graph = build_current(profile)
        ids = [n.id for n in graph.nodes]
        for edge in graph.edges:
            assert ids.index(edge.source) < ids.index(edge.target)


class TestProposedGraph:
    def test_adds_components_declared_by_recommendations(self) -> None:
        profile, recommendations = _context()
        proposed = build_proposed(profile, recommendations)

        added = proposed.proposed_ids()
        assert added, "the sample report should gain at least one component"
        assert all(
            n.origin is Origin.PROPOSED for n in proposed.nodes if n.id in added
        )

    def test_never_loses_a_component_the_report_described(self) -> None:
        profile, recommendations = _context()
        current = build_current(profile)
        proposed = build_proposed(profile, recommendations)
        assert {n.id for n in current.nodes} <= {n.id for n in proposed.nodes}

    def test_with_no_recommendations_it_equals_the_current_graph(self) -> None:
        profile, _ = _context()
        proposed = build_proposed(profile, [])
        current = build_current(profile)

        assert {n.id for n in proposed.nodes} == {n.id for n in current.nodes}
        assert proposed.proposed_ids() == set()

    def test_proposed_nodes_are_styled_distinctly(self) -> None:
        """A reader must be able to tell proposed from existing."""
        profile, recommendations = _context()
        diagram = render(build_proposed(profile, recommendations))
        assert "classDef proposed" in diagram
        assert "class " in diagram


class TestView:
    def test_produces_two_valid_diagrams(self) -> None:
        profile, recommendations = _context()
        view = build_view(profile, recommendations)

        validate(view.current_mermaid, view.current)
        validate(view.proposed_mermaid, view.proposed)

    def test_says_what_was_added(self) -> None:
        profile, recommendations = _context()
        view = build_view(profile, recommendations)
        assert view.added_components()

    def test_explains_that_a_missing_stage_means_undescribed(self) -> None:
        profile, recommendations = _context()
        notes = " ".join(build_view(profile, recommendations).notes).lower()
        assert "did not describe" in notes
