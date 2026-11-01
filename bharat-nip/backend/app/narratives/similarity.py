"""Lexical TF-IDF similarity over blinded claim text (NARRATIVE_INTELLIGENCE.md §3).

Speaker identity never enters: the text is `normalized_text` (speaker replaced by
[SPEAKER], which `terms` drops) plus subject and object.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Protocol

from app.domain.text import terms

Vector = dict[str, float]


def claim_text(normalized_text: str, subject: str | None, obj: str | None) -> str:
    return " ".join(x for x in (normalized_text, subject, obj) if x)


def _weight(term: str) -> float:
    return 2.0 if any(ch.isdigit() for ch in term) else 1.0


class SimilarityBackend(Protocol):
    def fit(self, documents: Mapping[str, str]) -> None: ...

    def vector(self, key: str) -> Vector: ...

    def vectorize(self, text: str) -> Vector: ...


class TfidfSimilarity:
    """Smoothed TF-IDF, numeric terms x2, L2-normalised sparse vectors."""

    def __init__(self) -> None:
        self.idf: dict[str, float] = {}
        self.vectors: dict[str, Vector] = {}

    def fit(self, documents: Mapping[str, str]) -> None:
        tokenized = {k: Counter(_tokens(v)) for k, v in documents.items()}
        n = len(tokenized)
        df: Counter[str] = Counter()
        for counts in tokenized.values():
            df.update(counts.keys())
        self.idf = {t: math.log((1 + n) / (1 + d)) + 1.0 for t, d in df.items()}
        self.vectors = {k: self._vec(c) for k, c in tokenized.items()}

    def _vec(self, counts: Counter[str]) -> Vector:
        default_idf = max(self.idf.values(), default=1.0)
        raw = {t: c * self.idf.get(t, default_idf) * _weight(t) for t, c in counts.items()}
        return normalize(raw)

    def vector(self, key: str) -> Vector:
        return self.vectors.get(key, {})

    def vectorize(self, text: str) -> Vector:
        return self._vec(Counter(_tokens(text)))


def _tokens(text: str) -> list[str]:
    # `terms` returns a set; repeated words in one claim are rare and unimportant here.
    return sorted(terms(text))


def normalize(v: Mapping[str, float]) -> Vector:
    norm = math.sqrt(sum(x * x for x in v.values()))
    return {k: x / norm for k, x in v.items()} if norm else {}


def cosine(a: Mapping[str, float], b: Mapping[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return round(sum(x * b.get(k, 0.0) for k, x in a.items()), 6)


def centroid(vectors: Iterable[Mapping[str, float]]) -> Vector:
    total: dict[str, float] = {}
    for v in vectors:
        for k, x in v.items():
            total[k] = total.get(k, 0.0) + x
    return normalize(total)


def top_terms(v: Mapping[str, float], n: int = 3) -> list[str]:
    return [t for t, _ in sorted(v.items(), key=lambda kv: (-kv[1], kv[0]))[:n]]


def greedy_cluster(
    keys: list[str], vectors: Mapping[str, Vector], threshold: float
) -> list[list[str]]:
    """Deterministic centroid-linkage clustering in the given order."""
    clusters: list[list[str]] = []
    centroids: list[Vector] = []
    for key in keys:
        v = vectors[key]
        best, best_sim = -1, threshold
        for i, c in enumerate(centroids):
            s = cosine(v, c)
            if s >= best_sim:
                best, best_sim = i, s
        if best >= 0:
            clusters[best].append(key)
            centroids[best] = centroid(vectors[k] for k in clusters[best])
        else:
            clusters.append([key])
            centroids.append(v)
    return clusters


def label_terms(v: Mapping[str, float], n: int = 3) -> list[str]:
    """Top terms for a human-readable label: words first, numbers only to fill up."""
    ranked = top_terms(v, len(v))
    words = [t for t in ranked if not any(ch.isdigit() for ch in t)]
    numbers = [t for t in ranked if t not in words]
    return (words + numbers)[:n]
