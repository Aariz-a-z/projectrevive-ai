"""Text similarity, behind a swappable interface.

Two backends, chosen by the EMBEDDER setting:

- `TfidfEmbedder` (default) uses scikit-learn only. It adds no weight to the
  deployment and runs anywhere, which is why it is the default rather than a
  fallback.
- `SentenceTransformerEmbedder` uses real sentence embeddings and understands
  paraphrase, which TF-IDF cannot. It pulls in PyTorch, so it is an optional
  extra rather than a dependency.

Keeping both behind one interface is also what makes the evaluation in README
section 8 possible: the TF-IDF backend is the content-only baseline the hybrid
engine has to be measured against, so the comparison is between two real
implementations rather than against a strawman.
"""

from __future__ import annotations

import logging
import re
from typing import Protocol

import numpy as np

logger = logging.getLogger(__name__)


class Embedder(Protocol):
    name: str

    def similarities(self, query: str, documents: list[str]) -> list[float]:
        """Similarity of `query` to each document, each in [0, 1]."""
        ...


def _cosine(query_vec: np.ndarray, doc_matrix: np.ndarray) -> list[float]:
    query_norm = np.linalg.norm(query_vec)
    doc_norms = np.linalg.norm(doc_matrix, axis=1)
    denom = doc_norms * query_norm
    # A zero vector means no shared vocabulary; similarity is 0, not NaN.
    with np.errstate(divide="ignore", invalid="ignore"):
        scores = np.where(denom > 0, (doc_matrix @ query_vec) / denom, 0.0)
    return [float(np.clip(s, 0.0, 1.0)) for s in scores]


class TfidfEmbedder:
    """Lexical similarity over the knowledge base corpus.

    The vectoriser is fitted on the documents *and* the query together. With a
    corpus this small, fitting on documents alone would drop any query term
    that happens not to appear in the knowledge base, which silently discards
    the most distinctive words in a project description.
    """

    name = "tfidf"

    def __init__(self) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer

        self._make_vectoriser = lambda: TfidfVectorizer(
            lowercase=True,
            stop_words="english",
            ngram_range=(1, 2),
            sublinear_tf=True,
            min_df=1,
        )

    def similarities(self, query: str, documents: list[str]) -> list[float]:
        if not documents:
            return []
        if not query.strip():
            return [0.0] * len(documents)

        vectoriser = self._make_vectoriser()
        matrix = vectoriser.fit_transform([*documents, query]).toarray()
        return _cosine(matrix[-1], matrix[:-1])


class SentenceTransformerEmbedder:
    """Semantic similarity. Requires the `semantic` extra (pulls in PyTorch)."""

    name = "sentence_transformer"

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - depends on extras
            raise RuntimeError(
                "EMBEDDER is set to 'sentence_transformer' but "
                "sentence-transformers is not installed. Install the extra "
                "with: pip install -e '.[semantic]'"
            ) from exc
        self._model = SentenceTransformer(model_name)

    def similarities(self, query: str, documents: list[str]) -> list[float]:
        if not documents:
            return []
        vectors = self._model.encode([*documents, query], convert_to_numpy=True)
        return _cosine(vectors[-1], vectors[:-1])


_WORD = re.compile(r"[a-z0-9]+")


def normalise(text: str) -> str:
    """Lowercase alphanumeric tokens, for stable matching input."""
    return " ".join(_WORD.findall(text.lower()))


def get_embedder(name: str) -> Embedder:
    if name == "sentence_transformer":
        return SentenceTransformerEmbedder()
    if name != "tfidf":
        logger.warning("unknown embedder %r, falling back to tfidf", name)
    return TfidfEmbedder()
