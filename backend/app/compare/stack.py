"""Building the current-versus-proposed stack comparison.

Everything here is derived from two things that already exist: the technology
the report names, with the pages it names them on, and the dependencies the
ranked recommendations would introduce. No model is involved, so this works on
the mock provider and cannot invent a library the report never mentioned.
"""

from __future__ import annotations

from app.knowledge.loader import load_knowledge_base
from app.schemas.comparison import StackComparison, StackEntry, StackVerdict
from app.schemas.project import Claim, ProjectProfile
from app.schemas.recommendation import Recommendation

# Dependencies that describe an environment rather than a project's stack.
# Recommending "docker" as an addition to a research project's library list
# is noise; it belongs in the deployment discussion.
INFRASTRUCTURE = {"docker"}


def _normalise(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def _current_entries(profile: ProjectProfile) -> list[StackEntry]:
    """One KEEP per technology the report actually names."""
    groups: list[tuple[str, list[Claim]]] = [
        ("language", profile.stack.languages),
        ("framework", profile.stack.frameworks),
        ("library", profile.stack.libraries),
        ("tool", profile.stack.tools),
    ]

    entries: list[StackEntry] = []
    for category, claims in groups:
        for claim in claims:
            if not claim.evidence:
                # Without a citation this is an inference about the stack, and
                # a "keep using X" verdict for something the report may never
                # have used would be worse than silence.
                continue
            entries.append(
                StackEntry(
                    name=claim.value,
                    category=category,
                    verdict=StackVerdict.KEEP,
                    evidence=claim.evidence,
                    rationale=(
                        f"The report uses {claim.value} and nothing in this "
                        "analysis gives a reason to change it. It is listed "
                        "so the decision to keep it is explicit rather than "
                        "an omission."
                    ),
                )
            )
    return entries


def compare_stack(
    profile: ProjectProfile, recommendations: list[Recommendation]
) -> StackComparison:
    """Current technologies, plus what the recommendations would introduce."""
    entries = _current_entries(profile)
    present = {_normalise(e.name) for e in entries}

    by_id = {entry.id: entry for entry in load_knowledge_base()}
    additions: dict[str, StackEntry] = {}

    for recommendation in recommendations:
        kb_entry = by_id.get(recommendation.id)
        replaces = getattr(kb_entry, "replaces", None) if kb_entry else None

        for dependency in recommendation.dependencies:
            key = _normalise(dependency)
            if key in present or key in INFRASTRUCTURE:
                continue

            existing = additions.get(key)
            if existing is not None:
                # Several recommendations wanting the same dependency is a
                # stronger case for it, so record all of them.
                if recommendation.id not in existing.introduced_by:
                    existing.introduced_by.append(recommendation.id)
                continue

            replacing = replaces if replaces in present else None
            additions[key] = StackEntry(
                name=dependency,
                category="library",
                verdict=(
                    StackVerdict.REPLACE if replacing else StackVerdict.ADD
                ),
                replaces=replacing,
                introduced_by=[recommendation.id],
                migration_complexity=recommendation.complexity,
                cost=recommendation.cost,
                rationale=(
                    f"Needed by: {recommendation.title}. "
                    f"{recommendation.reason}"
                ),
            )

    entries.extend(additions.values())

    notes = [
        "Nothing is marked for replacement because it is old. A technology "
        "only appears as a replacement when a recommendation names what it "
        "replaces and why.",
        "'Keep' is a verdict, not an absence of one: these are technologies "
        "the analysis examined and found no reason to change.",
    ]
    if not recommendations:
        notes.append(
            "No recommendations were produced, so nothing is proposed here."
        )
    elif not additions:
        notes.append(
            "The recommendations need no libraries the report does not "
            "already use. They are changes to method, not to tooling."
        )

    return StackComparison(entries=entries, notes=notes)
