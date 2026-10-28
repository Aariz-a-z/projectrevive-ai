"""Rendering a ComponentGraph as Mermaid, and checking the result.

Two separate jobs, deliberately kept apart:

- `render` turns a validated graph into Mermaid text, escaping every label so
  a dataset called `MNIST (handwritten)` cannot close a bracket early and
  corrupt the diagram.
- `validate` reads that text back and checks it structurally. Rendering and
  checking with the same assumptions would prove nothing, so the validator
  parses the output rather than trusting the renderer.

README section 4.6 asks for valid diagrams and useful error handling when
rendering fails. The backend refuses to emit a diagram it cannot parse back,
and the frontend has its own error boundary for the case where Mermaid itself
rejects something this never anticipated.
"""

from __future__ import annotations

import re

from app.schemas.architecture import ComponentGraph, NodeKind, Origin

#: Characters that terminate a Mermaid node label early or change the shape of
#: the node. Replaced rather than stripped so the text stays readable.
_LABEL_REPLACEMENTS = {
    '"': "'",
    "[": "(",
    "]": ")",
    "{": "(",
    "}": ")",
    "|": "/",
    "<": "",
    ">": "",
    "\n": " ",
    "\r": " ",
    ";": ",",
}

#: Shapes carry meaning: data stores are cylinders, decisions rounded, and so
#: on. Kept here rather than inline so the mapping is readable in one place.
_SHAPE = {
    NodeKind.DATA: ("[(", ")]"),
    NodeKind.STORAGE: ("[(", ")]"),
    NodeKind.PREPROCESS: ("[", "]"),
    NodeKind.FEATURES: ("[", "]"),
    NodeKind.MODEL: ("([", "])"),
    NodeKind.EVALUATION: ("{{", "}}"),
    NodeKind.SERVING: ("[/", "/]"),
    NodeKind.MONITORING: ("[/", "/]"),
}

_LINE = re.compile(
    r"^\s*(?P<src>[A-Za-z][A-Za-z0-9_]*)\s*-->\s*"
    r"(?:\|[^|]*\|\s*)?(?P<dst>[A-Za-z][A-Za-z0-9_]*)\s*$"
)
_NODE_LINE = re.compile(r"^\s*(?P<id>[A-Za-z][A-Za-z0-9_]*)\s*[\[(\{/]")


class MermaidError(RuntimeError):
    """The rendered diagram did not survive being read back."""


def escape_label(text: str) -> str:
    for bad, good in _LABEL_REPLACEMENTS.items():
        text = text.replace(bad, good)
    return " ".join(text.split()).strip() or "unnamed"


def render(graph: ComponentGraph) -> str:
    """Render the graph, then refuse to return anything that will not parse."""
    lines = ["flowchart TD"]

    for node in graph.nodes:
        open_shape, close_shape = _SHAPE.get(node.kind, ("[", "]"))
        label = escape_label(node.label)
        if node.detail:
            label = f"{label}<br/>{escape_label(node.detail)}"
        lines.append(f'    {node.id}{open_shape}"{label}"{close_shape}')

    for edge in graph.edges:
        if edge.label:
            lines.append(
                f"    {edge.source} -->|{escape_label(edge.label)}| {edge.target}"
            )
        else:
            lines.append(f"    {edge.source} --> {edge.target}")

    # Proposed components are styled so the diagram reads as before-and-after
    # without needing a second diagram beside it.
    proposed = sorted(graph.proposed_ids())
    if proposed:
        lines.append(
            "    classDef proposed stroke-dasharray: 4 3,stroke-width:2px;"
        )
        lines.append(f"    class {','.join(proposed)} proposed;")

    diagram = "\n".join(lines)
    validate(diagram, graph)
    return diagram


def validate(diagram: str, graph: ComponentGraph | None = None) -> None:
    """Read the diagram back and raise if it is not what it should be.

    This is a structural check, not a full Mermaid parser. It catches the
    failures this renderer could actually produce -- a label that broke out of
    its brackets, an edge to a node that was never declared -- rather than
    pretending to validate the whole grammar.
    """
    lines = [line for line in diagram.splitlines() if line.strip()]
    if not lines or not lines[0].startswith("flowchart"):
        raise MermaidError("diagram does not begin with a flowchart header")

    declared: set[str] = set()
    referenced: set[str] = set()

    for line in lines[1:]:
        stripped = line.strip()
        if stripped.startswith(("classDef", "class ", "%%")):
            continue

        edge = _LINE.match(stripped)
        if edge:
            referenced.update({edge.group("src"), edge.group("dst")})
            continue

        node = _NODE_LINE.match(stripped)
        if node:
            declared.add(node.group("id"))
            if stripped.count('"') % 2 != 0:
                raise MermaidError(
                    f"unbalanced quotes in node line: {stripped!r}"
                )
            continue

        raise MermaidError(f"unrecognised line in rendered diagram: {stripped!r}")

    dangling = referenced - declared
    if dangling:
        raise MermaidError(
            f"edges reference undeclared nodes: {sorted(dangling)}"
        )

    if graph is not None:
        expected = {n.id for n in graph.nodes}
        if declared != expected:
            raise MermaidError(
                "rendered nodes do not match the graph: "
                f"missing {sorted(expected - declared)}, "
                f"unexpected {sorted(declared - expected)}"
            )
