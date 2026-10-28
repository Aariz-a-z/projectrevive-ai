"""Deterministic stand-in for a real model.

This is not a fake that returns a canned blob. It reads the document, finds
what it can with keyword and structural heuristics, and cites the page it found
each item on. That means the whole pipeline -- extraction, validation,
recommendation, ranking, export -- can be built and tested end to end with no
API key and no spend, and the output still reflects the uploaded file.

Everything it produces is labelled as coming from the mock provider, so a
deterministic guess can never be mistaken for a real analysis.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from app.errors import LLMUnavailable
from app.llm.base import StructuredResult, Usage
from app.schemas.project import (
    Claim,
    ClaimSource,
    DatasetInfo,
    EvaluationInfo,
    Evidence,
    ProjectProfile,
    TechStack,
)

MOCK_NOTE = (
    "This profile was produced by the deterministic mock provider, not by a "
    "language model. It reflects keyword matches in the document, not "
    "comprehension of it. Set LLM_PROVIDER=anthropic for a real analysis."
)

_PAGE_MARKER = re.compile(r"^\[page (\d+)\]$", re.M)

ALGORITHMS = [
    "CNN", "convolutional neural network", "RNN", "LSTM", "GRU", "transformer",
    "BERT", "ResNet", "VGG", "YOLO", "random forest", "decision tree",
    "logistic regression", "linear regression", "SVM", "support vector machine",
    "naive bayes", "k-means", "KNN", "k-nearest", "XGBoost", "gradient boosting",
    "autoencoder", "GAN", "reinforcement learning",
]
LIBRARIES = [
    "TensorFlow", "Keras", "PyTorch", "scikit-learn", "sklearn", "pandas",
    "NumPy", "OpenCV", "NLTK", "spaCy", "Matplotlib", "Seaborn", "Flask",
    "Django", "Streamlit", "FastAPI", "XGBoost", "Hugging Face",
]
LANGUAGES = ["Python", "Java", "JavaScript", "TypeScript", "C++", "MATLAB"]
METRICS = [
    "accuracy", "precision", "recall", "F1", "F1-score", "AUC", "ROC",
    "RMSE", "MAE", "MSE", "confusion matrix", "mean average precision",
]
DOMAIN_HINTS = {
    "computer vision": ["image", "CNN", "OpenCV", "ResNet", "YOLO", "segmentation"],
    "natural language processing": ["text", "NLP", "BERT", "sentiment", "token", "spaCy"],
    "recommendation systems": ["recommend", "collaborative filtering", "user-item"],
    "time series / forecasting": ["forecast", "time series", "ARIMA", "LSTM"],
    "tabular machine learning": ["dataset", "feature", "classifier", "regression"],
}


def _split_pages(text: str) -> list[tuple[int, str]]:
    """Recover (page_number, text) pairs from marker-annotated prompt text."""
    matches = list(_PAGE_MARKER.finditer(text))
    pages: list[tuple[int, str]] = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        pages.append((int(match.group(1)), text[match.end():end].strip()))
    if not pages:
        pages = [(1, text.strip())]
    return pages


def _sentence_containing(page_text: str, needle: str) -> str:
    """The sentence a keyword appears in, for use as an evidence quote."""
    flat = " ".join(page_text.split())
    parts = re.split(r"(?<=[.!?])\s+", flat)
    low = needle.lower()
    for part in parts:
        if low in part.lower():
            return part[:600]
    return flat[:600] or needle


def _find(pages: list[tuple[int, str]], terms: list[str]) -> list[Claim]:
    """One STATED claim per term found, deduplicated, with page evidence."""
    claims: list[Claim] = []
    seen: set[str] = set()
    for term in terms:
        key = term.strip().lower()
        if key in seen:
            continue
        for page_no, page_text in pages:
            if re.search(rf"\b{re.escape(term.strip())}\b", page_text, re.I):
                seen.add(key)
                claims.append(
                    Claim(
                        value=term.strip(),
                        source=ClaimSource.STATED,
                        evidence=[
                            Evidence(
                                page=page_no,
                                quote=_sentence_containing(page_text, term.strip()),
                            )
                        ],
                    )
                )
                break
    return claims


def _title(pages: list[tuple[int, str]]) -> Claim:
    first_page, first_text = pages[0]
    for line in first_text.splitlines():
        candidate = line.strip()
        if 10 <= len(candidate) <= 120 and not candidate.lower().startswith("page "):
            return Claim(
                value=candidate,
                source=ClaimSource.STATED,
                evidence=[Evidence(page=first_page, quote=candidate)],
            )
    return Claim(
        value="Untitled project",
        source=ClaimSource.INFERRED,
        reasoning="No short heading line was found near the start of the document.",
    )


def _problem_statement(pages: list[tuple[int, str]]) -> Claim:
    for page_no, page_text in pages:
        for para in re.split(r"\n\s*\n", page_text):
            flat = " ".join(para.split())
            if len(flat) >= 120:
                return Claim(
                    value=flat[:600],
                    source=ClaimSource.STATED,
                    evidence=[Evidence(page=page_no, quote=flat[:600])],
                )
    return Claim(
        value="Not stated in the report.",
        source=ClaimSource.INFERRED,
        reasoning="No paragraph long enough to read as a problem statement was found.",
    )


def _domain(pages: list[tuple[int, str]]) -> Claim:
    blob = " ".join(text for _, text in pages).lower()
    best, score = None, 0
    for domain, hints in DOMAIN_HINTS.items():
        hits = sum(1 for h in hints if h.lower() in blob)
        if hits > score:
            best, score = domain, hits
    if best is None:
        return Claim(
            value="unknown",
            source=ClaimSource.INFERRED,
            reasoning="No domain keywords matched.",
        )
    return Claim(
        value=best,
        source=ClaimSource.INFERRED,
        reasoning=f"{score} keyword(s) associated with {best} appear in the document.",
    )


def _limitations(pages: list[tuple[int, str]]) -> list[Claim]:
    claims: list[Claim] = []
    pattern = re.compile(r"limitation|drawback|shortcoming|future work", re.I)
    for page_no, page_text in pages:
        flat = " ".join(page_text.split())
        for sentence in re.split(r"(?<=[.!?])\s+", flat):
            # Skip section headings like "4. Limitations." -- they match the
            # keyword but carry no content.
            if len(sentence) < 40:
                continue
            if pattern.search(sentence):
                claims.append(
                    Claim(
                        value=sentence[:600],
                        source=ClaimSource.STATED,
                        evidence=[Evidence(page=page_no, quote=sentence[:600])],
                    )
                )
    return claims[:10]


def build_project_profile(document_text: str) -> ProjectProfile:
    pages = _split_pages(document_text)
    notes = [MOCK_NOTE]

    algorithms = _find(pages, ALGORITHMS)
    metrics = _find(pages, METRICS)
    if not algorithms:
        notes.append("No recognised algorithm names were found in the document.")
    if not metrics:
        notes.append("No recognised evaluation metrics were found in the document.")

    return ProjectProfile(
        title=_title(pages),
        domain=_domain(pages),
        problem_statement=_problem_statement(pages),
        algorithms=algorithms,
        stack=TechStack(
            languages=_find(pages, LANGUAGES),
            libraries=_find(pages, LIBRARIES),
        ),
        dataset=DatasetInfo(),
        evaluation=EvaluationInfo(metrics=metrics),
        stated_limitations=_limitations(pages),
        extraction_notes=notes,
    )


_BUILDERS: dict[type[BaseModel], object] = {ProjectProfile: build_project_profile}


class MockProvider:
    """Implements app.llm.base.LLMProvider."""

    name = "mock"
    model = "mock-deterministic-v1"

    def structured(
        self,
        *,
        system: str,
        document: str,
        schema: type[BaseModel],
        task: str = "",
    ) -> StructuredResult:
        builder = _BUILDERS.get(schema)
        if builder is None:
            raise LLMUnavailable(
                f"The mock provider cannot produce {schema.__name__}. "
                "Set LLM_PROVIDER=anthropic to use a real model for this step."
            )
        parsed = builder(document)  # type: ignore[operator]
        return StructuredResult(
            parsed=parsed,
            provider=self.name,
            model=self.model,
            usage=Usage(),
            warnings=[MOCK_NOTE],
        )
