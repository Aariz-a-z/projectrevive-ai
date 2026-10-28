"""Matching knowledge base entries to a project.

Two signals, kept separate because they are not equally strong:

- **Knowledge linkage.** A rule detected a specific problem, and an entry
  declares that it fixes exactly that rule. This is the strongest connection
  available: it is traceable to a quote in the user's own report.
- **Content similarity.** The entry's text resembles the project description.
  This is a guess. It can surface genuinely relevant ideas no rule covers, and
  it can also match on shared vocabulary alone.

Relevance is weighted accordingly, and content-only matches are capped below
anything a finding supports. Ranking them equally would put a plausible-looking
guess above a recommendation that cites the user's own page.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.knowledge.schema import KBEntry
from app.recommend.embed import Embedder, normalise
from app.schemas.findings import Finding, Severity
from app.schemas.project import ProjectProfile
from app.schemas.recommendation import MatchedBy

# How strongly a finding supports an entry, by how the two were connected.
LINK_RULE = 1.0
LINK_CATEGORY = 0.6

SEVERITY_WEIGHT = {
    Severity.HIGH: 1.0,
    Severity.MEDIUM: 0.8,
    Severity.LOW: 0.6,
}

# Content similarity alone cannot exceed this, so a lexical coincidence never
# outranks something grounded in a detected finding.
CONTENT_ONLY_CEILING = 0.45
# Below this share of the best match, a content score is noise rather than
# signal. Expressed relative to the batch, not as a raw similarity: see
# `_relative_scores`.
CONTENT_FLOOR = 0.25
# If even the best raw similarity is this low, nothing in the knowledge base
# resembles the project and the whole content signal is discarded.
MIN_USEFUL_SIMILARITY = 0.01


@dataclass
class Candidate:
    entry: KBEntry
    knowledge_score: float
    content_score: float
    matched_findings: list[Finding] = field(default_factory=list)

    @property
    def matched_by(self) -> MatchedBy:
        has_knowledge = self.knowledge_score > 0
        has_content = self.content_score >= CONTENT_FLOOR
        if has_knowledge and has_content:
            return MatchedBy.BOTH
        if has_knowledge:
            return MatchedBy.KNOWLEDGE
        return MatchedBy.CONTENT

    @property
    def relevance(self) -> float:
        """Combined relevance in [0, 1].

        With a finding behind it, knowledge dominates and content refines.
        Without one, the score is capped: similarity is a weaker claim.
        """
        if self.knowledge_score > 0:
            return min(
                1.0, 0.7 * self.knowledge_score + 0.3 * self.content_score
            )
        return min(CONTENT_ONLY_CEILING, self.content_score)


def project_text(profile: ProjectProfile, findings: list[Finding]) -> str:
    """The query side of content matching.

    Built from the structured profile plus finding titles rather than the raw
    document, so matching is against what the project *is* rather than against
    whichever words happen to be frequent in a long report.
    """
    parts = [
        profile.title.value,
        profile.domain.value,
        profile.problem_statement.value,
        *(c.value for c in profile.algorithms),
        *(c.value for c in profile.stack.libraries),
        *(c.value for c in profile.stack.frameworks),
        *(c.value for c in profile.evaluation.metrics),
        *(c.value for c in profile.stated_limitations),
        *(f.title for f in findings),
        *(f.category.value.replace("_", " ") for f in findings),
    ]
    return normalise(" ".join(parts))


def _knowledge_score(entry: KBEntry, findings: list[Finding]) -> tuple[float, list[Finding]]:
    """Best link between this entry and any finding, plus what matched."""
    best = 0.0
    matched: list[Finding] = []

    for finding in findings:
        strength = 0.0
        if finding.rule_id and finding.rule_id in entry.addresses_rules:
            strength = LINK_RULE
        elif finding.category in entry.addresses_categories:
            strength = LINK_CATEGORY
        elif finding.category is entry.category:
            strength = LINK_CATEGORY

        if strength == 0.0:
            continue

        matched.append(finding)
        best = max(best, strength * SEVERITY_WEIGHT[finding.severity])

    # Most severe first, so the citation shown is the strongest one.
    matched.sort(key=lambda f: f.sort_key)
    return best, matched


def _relative_scores(raw: list[float]) -> list[float]:
    """Rescale raw similarities to a share of the best match in the batch.

    Absolute cosine values are not comparable across embedders: TF-IDF on
    short text produces roughly 0.0-0.2, while sentence-transformers produce
    0.3-0.9 for the same pair. A fixed threshold or weight tuned for one would
    be meaningless for the other, which would defeat the point of making the
    embedder swappable.

    Content similarity is a comparative question anyway -- which entries are
    most like this project -- so expressing it as a share of the top match is
    both scale-free and closer to what the number actually means. It does mean
    the score is relative, never an absolute claim of similarity, and the UI
    labels it that way.
    """
    if not raw:
        return []
    best = max(raw)
    if best < MIN_USEFUL_SIMILARITY:
        return [0.0] * len(raw)
    return [value / best for value in raw]


def find_candidates(
    profile: ProjectProfile,
    findings: list[Finding],
    entries: tuple[KBEntry, ...],
    embedder: Embedder,
) -> list[Candidate]:
    """Score every knowledge base entry against this project."""
    if not entries:
        return []

    query = project_text(profile, findings)
    documents = [normalise(entry.match_text()) for entry in entries]
    similarities = _relative_scores(embedder.similarities(query, documents))

    candidates: list[Candidate] = []
    for entry, similarity in zip(entries, similarities, strict=True):
        knowledge, matched = _knowledge_score(entry, findings)
        if knowledge == 0.0 and similarity < CONTENT_FLOOR:
            continue  # neither signal says anything
        candidates.append(
            Candidate(
                entry=entry,
                knowledge_score=knowledge,
                content_score=similarity,
                matched_findings=matched,
            )
        )

    return candidates
