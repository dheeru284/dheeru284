"""Deterministic compliance rules for draft public information (AGENT_ORGANIZATION.md §6).

These are heuristics with a bias to block: a false positive costs a human a minute, a false
negative could put misleading or manipulative content in front of the public.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from app.org.policy import AI_ASSISTED_LABEL
from app.org.schemas import CitedSentence, ComplianceOutput, ContentDraft, Translation

NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)*")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?:\+?\d[\d\s-]{8,}\d)")
TARGETING = (
    "voters who are",
    "voters from the",
    "people of caste",
    "members of the community",
    "target audience",
    "targeted at",
    "micro-target",
    "swing voters",
    "persuadable",
)
CALL_TO_VOTE = re.compile(
    r"\b(vote (?:for|against)|don't vote|do not vote for|defeat (?:the )?\w+ party|"
    r"elect \w+|support (?:the )?\w+ party)\b",
    re.IGNORECASE,
)
IMPERSONATION = re.compile(
    r"\b(?:I am|I'm|This is)\s+(?:Minister|Shri|Smt|Dr|Mr|Ms|Mrs)\b", re.IGNORECASE
)
PUBLISH_INSTRUCTION = re.compile(
    r"\b(post (?:this|it) (?:on|to)|schedule (?:this|the post)|auto-?post|send to all|"
    r"forward to (?:all|every))\b",
    re.IGNORECASE,
)


def numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in NUMBER.findall(text)}


def ungrounded_numbers(sentence: CitedSentence, facts: dict[str, str]) -> set[str]:
    """Numbers in the sentence that appear in none of its cited facts."""
    grounded: set[str] = set()
    for label in sentence.citations:
        grounded |= numbers(facts.get(label, ""))
    return numbers(sentence.text) - grounded


def fact_texts(facts: Iterable[dict]) -> dict[str, str]:
    return {
        f["label"]: " ".join([f.get("claim", ""), f.get("summary", ""), *f.get("quotes", [])])
        for f in facts
    }


def check(
    draft: ContentDraft, translations: list[Translation], facts: list[dict]
) -> ComplianceOutput:
    violations: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    known = fact_texts(facts)

    def v(rule: str, detail: str, where: str) -> None:
        violations.append({"rule": rule, "detail": detail, "location": where})

    if draft.ai_assisted_label != AI_ASSISTED_LABEL:
        v("ai_label", "The AI-assisted label is missing or altered.", "draft")
    if draft.format == "NONE":
        warnings.append(
            {
                "rule": "no_response",
                "detail": "No public response is recommended.",
                "location": "draft",
            }
        )
    texts = [("headline", draft.headline)] + [
        (f"sentence {i + 1}", s.text) for i, s in enumerate(draft.sentences)
    ]
    for t in translations:
        texts.append((f"{t.language} headline", t.headline))
        texts += [(f"{t.language} sentence {i + 1}", s.text) for i, s in enumerate(t.sentences)]

    for i, s in enumerate(draft.sentences, start=1):
        if not s.citations:
            v(
                "uncited_sentence",
                "Every sentence must cite an approved fact-check.",
                f"sentence {i}",
            )
        unknown = [c for c in s.citations if c not in known]
        if unknown:
            v(
                "unknown_citation",
                f"Cites {unknown}, which are not approved facts.",
                f"sentence {i}",
            )
        extra = ungrounded_numbers(s, known)
        if extra:
            v(
                "ungrounded_number",
                f"Numbers {sorted(extra)} do not appear in cited facts.",
                f"sentence {i}",
            )
    for where, text in texts:
        low = text.lower()
        if EMAIL.search(text) or PHONE.search(text):
            v("personal_data", "Contains an email address or phone number.", where)
        if any(t in low for t in TARGETING):
            v("targeting", "Contains demographic or individual targeting language.", where)
        if CALL_TO_VOTE.search(text):
            v("call_to_vote", "Fact-check communications must not tell people how to vote.", where)
        if IMPERSONATION.search(text):
            v("impersonation", "First-person statement attributed to a named person.", where)
        if PUBLISH_INSTRUCTION.search(text):
            v(
                "publish_instruction",
                "Drafts may not contain posting or sending instructions.",
                where,
            )
    for t in translations:
        if len(t.sentences) != len(draft.sentences):
            v("translation_shape", "Translation sentence count differs from the draft.", t.language)
            continue
        for i, (src, dst) in enumerate(zip(draft.sentences, t.sentences, strict=True), 1):
            if sorted(src.citations) != sorted(dst.citations):
                v(
                    "translation_citations",
                    "Citations changed in translation.",
                    f"{t.language} sentence {i}",
                )
            if numbers(src.text) != numbers(dst.text):
                v(
                    "translation_numbers",
                    "Numbers changed in translation.",
                    f"{t.language} sentence {i}",
                )
    return ComplianceOutput(passed=not violations, violations=violations, warnings=warnings)
