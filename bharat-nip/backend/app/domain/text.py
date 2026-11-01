"""Deterministic text utilities used by the pipeline. No LLM involved, fully testable."""

from __future__ import annotations

import re
from dataclasses import dataclass

SPEAKER_PLACEHOLDER = "[SPEAKER]"
_WORD = re.compile(r"[a-z0-9]+(?:[.,][0-9]+)*", re.IGNORECASE)
STOPWORDS = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "but",
        "by",
        "for",
        "from",
        "had",
        "has",
        "have",
        "he",
        "her",
        "his",
        "i",
        "in",
        "into",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "our",
        "over",
        "said",
        "says",
        "she",
        "so",
        "than",
        "that",
        "the",
        "their",
        "them",
        "there",
        "these",
        "they",
        "this",
        "those",
        "to",
        "under",
        "up",
        "was",
        "we",
        "were",
        "what",
        "when",
        "which",
        "who",
        "will",
        "with",
        "would",
        "you",
        "your",
        "speaker",
        "organization",
        "claimed",
        "claims",
        "stated",
        "states",
        "according",
    ]
)

# --- attribution blinding ----------------------------------------------------------------


def blind(text: str, speaker_names: list[str]) -> str:
    """Replace speaker names with [SPEAKER] (case-insensitive, whole words, possessives).

    Longest names first, so "Ministry of Finance" is replaced before "Finance".
    """
    result = text
    for name in sorted(
        {n.strip() for n in speaker_names if n and n.strip()}, key=len, reverse=True
    ):
        pattern = re.compile(rf"(?<!\w){re.escape(name)}(?:'s|\u2019s)?(?!\w)", re.IGNORECASE)
        result = pattern.sub(SPEAKER_PLACEHOLDER, result)
    return result


def strip_placeholders(text: str) -> str:
    return re.sub(r"\[[A-Z_]+\]", " ", text)


# --- lexical relevance -------------------------------------------------------------------


def terms(text: str) -> set[str]:
    out = set()
    for match in _WORD.finditer(strip_placeholders(text).lower()):
        w = match.group(0).rstrip(".,")
        if (len(w) > 2 or w.isdigit()) and w not in STOPWORDS:
            out.add(w)
    return out


def lexical_relevance(claim_text: str, passage: str) -> float:
    """Share of the claim's content terms found in the passage; numbers count double
    because factual claims usually turn on them. Returns 0..1."""
    claim_terms = terms(claim_text)
    if not claim_terms:
        return 0.0
    passage_terms = terms(passage)

    def weight(t: str) -> float:
        return 2.0 if any(ch.isdigit() for ch in t) else 1.0

    total = sum(weight(t) for t in claim_terms)
    hit = sum(weight(t) for t in claim_terms if t in passage_terms)
    return round(hit / total, 4)


def grounding_score(claim_text: str, material: str) -> float:
    """How much of an extracted claim's wording appears in the source material."""
    return lexical_relevance(claim_text, material)


# --- chunking ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Chunk:
    index: int
    start: int
    end: int
    text: str


def _paragraph_spans(text: str) -> list[tuple[int, int]]:
    """(start, end) of each paragraph, trimmed of surrounding whitespace."""
    spans: list[tuple[int, int]] = []
    pos = 0
    for sep in [*re.finditer(r"\n\s*\n", text), None]:
        seg_end = sep.start() if sep else len(text)
        start, end = pos, seg_end
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if end > start:
            spans.append((start, end))
        if sep:
            pos = sep.end()
    return spans


def chunk_text(text: str, target_chars: int = 1200) -> list[Chunk]:
    """Split on paragraph boundaries into ~target_chars chunks with exact offsets, so that
    ``text[chunk.start:chunk.end] == chunk.text`` always holds."""
    chunks: list[Chunk] = []
    paragraphs = _paragraph_spans(text)
    cur_start: int | None = None
    cur_end = 0
    for p_start, p_end in paragraphs:
        if cur_start is None:
            cur_start, cur_end = p_start, p_end
        elif p_end - cur_start <= target_chars:
            cur_end = p_end
        else:
            chunks.append(Chunk(len(chunks), cur_start, cur_end, text[cur_start:cur_end]))
            cur_start, cur_end = p_start, p_end
        # A single very long paragraph is split on sentence-ish boundaries.
        while cur_end - cur_start > target_chars * 2:
            cut = text.rfind(". ", cur_start, cur_start + target_chars)
            cut = cut + 1 if cut > cur_start else cur_start + target_chars
            chunks.append(Chunk(len(chunks), cur_start, cut, text[cur_start:cut]))
            cur_start = cut
            while cur_start < cur_end and text[cur_start].isspace():
                cur_start += 1
    if cur_start is not None and cur_end > cur_start:
        chunks.append(Chunk(len(chunks), cur_start, cur_end, text[cur_start:cur_end]))
    return chunks


# --- verbatim quote location -------------------------------------------------------------


def locate_quote(haystack: str, quote: str) -> tuple[int, int] | None:
    """Find ``quote`` in ``haystack``. Exact match first; otherwise the same words in the
    same order allowing only whitespace differences (line breaks in PDFs/HTML). Returns
    offsets into ``haystack`` or None. Never matches paraphrases."""
    q = quote.strip()
    if not q:
        return None
    idx = haystack.find(q)
    if idx >= 0:
        return idx, idx + len(q)
    words = q.split()
    if not words:
        return None
    pattern = r"\s+".join(re.escape(w) for w in words)
    m = re.search(pattern, haystack)
    return (m.start(), m.end()) if m else None
