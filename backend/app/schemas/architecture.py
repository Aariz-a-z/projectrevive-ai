"""The component graph a diagram is rendered from.

README section 4.6 requires diagrams to be generated from structured project
data rather than from free-form model output. So the graph is the artefact and
the diagram is a rendering of it: the structure can be validated, diffed and
tested, and a rendering bug cannot invent a component that is not in the data.

The graph validates itself. An edge pointing at a node that does not exist
produces a diagram that either fails to parse or silently grows a phantom box,
and both are worse than refusing to build it.
"""

from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel, Field, model_validator

#: Mermaid node identifiers are bare words; anything else has to be quoted or
#: it changes the meaning of the line.
NODE_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


class NodeKind(str, Enum):
    """The component types README section 4.6 lists, in pipeline order.

    The declaration order matters: edges are built by connecting consecutive
    present kinds, so this is the canonical flow of a project.
    """

    DATA = "data"
    PREPROCESS = "preprocess"
    FEATURES = "features"
    MODEL = "model"
    EVALUATION = "evaluation"
    SERVING = "serving"
    MONITORING = "monitoring"
    STORAGE = "storage"


#: Pipeline order for edge building. Storage hangs off the model rather than
#: sitting in the chain, so it is excluded here and wired separately.
FLOW_ORDER = [
    NodeKind.DATA,
    NodeKind.PREPROCESS,
    NodeKind.FEATURES,
    NodeKind.MODEL,
    NodeKind.EVALUATION,
    NodeKind.SERVING,
    NodeKind.MONITORING,
]


class Origin(str, Enum):
    REPORT = "report"
    PROPOSED = "proposed"


class Node(BaseModel):
    id: str
    label: str = Field(min_length=1, max_length=80)
    kind: NodeKind
    origin: Origin
    detail: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _id_is_renderable(self) -> "Node":
        if not NODE_ID.match(self.id):
            raise ValueError(
                f"node id {self.id!r} is not a bare identifier; it would "
                "change the meaning of the rendered line"
            )
        return self


class Edge(BaseModel):
    source: str
    target: str
    label: str = Field(default="", max_length=40)


class ComponentGraph(BaseModel):
    title: str
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)

    @model_validator(mode="after")
    def _graph_is_coherent(self) -> "ComponentGraph":
        ids = [node.id for node in self.nodes]
        duplicates = {i for i in ids if ids.count(i) > 1}
        if duplicates:
            raise ValueError(f"duplicate node ids: {sorted(duplicates)}")

        known = set(ids)
        for edge in self.edges:
            missing = {edge.source, edge.target} - known
            if missing:
                raise ValueError(
                    f"edge {edge.source}->{edge.target} references unknown "
                    f"node(s): {sorted(missing)}"
                )
        return self

    def of_kind(self, kind: NodeKind) -> list[Node]:
        return [n for n in self.nodes if n.kind is kind]

    def proposed_ids(self) -> set[str]:
        return {n.id for n in self.nodes if n.origin is Origin.PROPOSED}


class ArchitectureView(BaseModel):
    """Before and after, as README section 4.8 asks for."""

    current: ComponentGraph
    proposed: ComponentGraph
    current_mermaid: str
    proposed_mermaid: str
    notes: list[str] = Field(default_factory=list)

    def added_components(self) -> list[str]:
        existing = {n.id for n in self.current.nodes}
        return [n.label for n in self.proposed.nodes if n.id not in existing]
