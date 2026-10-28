"""Building current and proposed component graphs.

The current graph is built only from what the report evidences. A project that
never describes evaluation does not get an evaluation box, because an
architecture diagram showing a step the project does not perform is a nicer
picture of a different project.

The proposed graph is the current one plus the components that recommendations
declare they add. Each knowledge base entry says which component it introduces,
so a new entry changes the diagram without anything else being edited.

One node per component kind. A flowchart with three separate evaluation boxes
is harder to read than one, and collapsing them keeps node ids stable.
"""

from __future__ import annotations

from app.schemas.architecture import (
    FLOW_ORDER,
    ComponentGraph,
    Edge,
    Node,
    NodeKind,
    Origin,
)
from app.schemas.project import ProjectProfile
from app.schemas.recommendation import Recommendation

#: Node ids are derived from the kind, so they are stable across rebuilds and
#: a diff between current and proposed is meaningful.
NODE_IDS = {kind: kind.value.capitalize() for kind in NodeKind}

PREPROCESS_TERMS = (
    "normalis", "normaliz", "standardis", "standardiz", "scaling",
    "augmentation", "cleaning", "encoding", "tokenis", "tokeniz", "reshap",
    "preprocess",
)


def _node(kind: NodeKind, label: str, origin: Origin, detail: str | None = None) -> Node:
    return Node(id=NODE_IDS[kind], label=label, kind=kind, origin=origin, detail=detail)


def _join(values: list[str], limit: int = 3) -> str:
    shown = values[:limit]
    extra = len(values) - len(shown)
    text = ", ".join(shown)
    return f"{text} +{extra} more" if extra > 0 else text


def _mentions_preprocessing(profile: ProjectProfile) -> bool:
    """Any claim in the profile describing a preprocessing step."""
    haystack = " ".join(claim.value for claim in profile.all_claims()).lower()
    return any(term in haystack for term in PREPROCESS_TERMS)


def build_current(profile: ProjectProfile) -> ComponentGraph:
    """What the report describes. Nothing is added for completeness."""
    nodes: list[Node] = []

    dataset = profile.dataset.name.value if profile.dataset.name else None
    nodes.append(
        _node(NodeKind.DATA, dataset or "Dataset", Origin.REPORT)
    )

    preprocessing = [c.value for c in profile.dataset.preprocessing]
    if preprocessing:
        nodes.append(
            _node(
                NodeKind.PREPROCESS, "Preprocessing", Origin.REPORT,
                _join(preprocessing),
            )
        )
    elif _mentions_preprocessing(profile):
        # The dedicated field is empty, but the report clearly describes the
        # step somewhere. Scanning the whole profile rather than one field
        # stops the diagram omitting a stage the project demonstrably has --
        # "images were normalised" usually lands in methodology, not in a
        # preprocessing list.
        nodes.append(_node(NodeKind.PREPROCESS, "Preprocessing", Origin.REPORT))

    algorithms = [c.value for c in profile.algorithms]
    nodes.append(
        _node(
            NodeKind.MODEL,
            "Model" if not algorithms else _join(algorithms),
            Origin.REPORT,
        )
    )

    metrics = [c.value for c in profile.evaluation.metrics]
    if metrics:
        nodes.append(
            _node(NodeKind.EVALUATION, "Evaluation", Origin.REPORT, _join(metrics))
        )

    return ComponentGraph(
        title="Architecture described in the report",
        nodes=nodes,
        edges=_flow_edges(nodes),
    )


def _flow_edges(nodes: list[Node]) -> list[Edge]:
    """Connect consecutive present kinds in the canonical pipeline order."""
    by_kind = {node.kind: node for node in nodes}
    present = [by_kind[k] for k in FLOW_ORDER if k in by_kind]

    edges = [
        Edge(source=a.id, target=b.id)
        for a, b in zip(present, present[1:], strict=False)
    ]

    # Storage is not a stage in the flow; it records what the model produces.
    storage = by_kind.get(NodeKind.STORAGE)
    model = by_kind.get(NodeKind.MODEL)
    if storage and model:
        edges.append(Edge(source=model.id, target=storage.id, label="records"))

    return edges


def build_proposed(
    profile: ProjectProfile, recommendations: list[Recommendation]
) -> ComponentGraph:
    """The current graph plus whatever the recommendations introduce."""
    from app.knowledge.loader import load_knowledge_base

    current = build_current(profile)
    nodes = list(current.nodes)
    present_kinds = {node.kind for node in nodes}

    by_id = {entry.id: entry for entry in load_knowledge_base()}

    # Recommendations arrive ranked, so the highest-scoring entry wins the
    # label when two propose the same kind of component.
    for recommendation in recommendations:
        entry = by_id.get(recommendation.id)
        component = entry.adds_component if entry else None
        if component is None or component.kind in present_kinds:
            continue
        present_kinds.add(component.kind)
        nodes.append(
            _node(
                component.kind, component.label, Origin.PROPOSED, component.detail
            )
        )

    return ComponentGraph(
        title="Architecture with the recommendations applied",
        nodes=nodes,
        edges=_flow_edges(nodes),
    )


def build_view(
    profile: ProjectProfile, recommendations: list[Recommendation]
) -> "ArchitectureView":
    """Both graphs plus their rendered diagrams, ready for the API."""
    from app.architecture.mermaid import render
    from app.schemas.architecture import ArchitectureView

    current = build_current(profile)
    proposed = build_proposed(profile, recommendations)

    notes = [
        "The current diagram shows only components the report evidences. A "
        "missing stage means the report did not describe it, not that the "
        "project lacks it.",
        "Dashed outlines are proposed components, each introduced by a "
        "recommendation rather than added to make the picture look complete.",
    ]
    added = [n.label for n in proposed.nodes if n.id not in {c.id for c in current.nodes}]
    if not added:
        notes.append(
            "The recommendations change method rather than structure, so the "
            "two diagrams are the same."
        )

    return ArchitectureView(
        current=current,
        proposed=proposed,
        current_mermaid=render(current),
        proposed_mermaid=render(proposed),
        notes=notes,
    )
