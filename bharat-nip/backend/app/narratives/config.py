"""Narrative engine constants (NARRATIVE_INTELLIGENCE.md). Changing any value requires a new
ENGINE_VERSION / RECOMMENDATION_VERSION."""

from __future__ import annotations

ENGINE_VERSION = "narr-v1"
RECOMMENDATION_VERSION = "rec-v1"

NARRATIVE_SIMILARITY = 0.45
TOPIC_SIMILARITY = 0.20
RELATION_SIMILARITY = 0.20
HISTORY_MATCH_SIMILARITY = 0.40
TOPIC_JACCARD_STABILITY = 0.5

MIN_NARRATIVE_CLAIMS = 2
MIN_NARRATIVE_SUBMISSIONS = 2

RECURRENCE_GAP_DAYS = 7
EMERGING_WINDOW_DAYS = 7
EMERGING_BASELINE_WEEKS = 4
EMERGING_MIN_RECENT = 3
ARCHIVE_AFTER_IDLE_DAYS = 30
STALE_RESPONSE_OCCURRENCES = 3

LOW, MEDIUM = 0.33, 0.66  # level boundaries: LOW < 0.33 <= MEDIUM < 0.66 <= HIGH
HIGH_COVERAGE = 0.7
LOW_COVERAGE = 0.3

# Non-binding harm signals: prompt an analyst to assess harm; they never set severity.
# About real-world consequences only, never about which side a narrative helps.
HARM_SIGNAL_LEXICON: dict[str, tuple[str, ...]] = {
    "PUBLIC_HEALTH": (
        "vaccine",
        "vaccination",
        "outbreak",
        "epidemic",
        "cure",
        "medicine",
        "hospital",
        "disease",
        "virus",
    ),
    "PUBLIC_SAFETY": (
        "riot",
        "attack",
        "bomb",
        "violence",
        "stampede",
        "flood",
        "evacuate",
        "curfew",
    ),
    "ELECTORAL_PROCESS": (
        "polling",
        "booth",
        "ballot",
        "voter id",
        "voting date",
        "evm",
        "election date",
        "counting",
    ),
    "COMMUNAL_HARMONY": ("communal", "mob", "lynch", "temple", "mosque", "church", "caste clash"),
    "FINANCIAL_FRAUD": ("scheme", "lottery", "otp", "bank account", "investment returns", "refund"),
}
