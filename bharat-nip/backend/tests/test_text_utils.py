import pytest

from app.domain.text import chunk_text, lexical_relevance, locate_quote, terms


def test_chunks_keep_exact_offsets():
    text = "Intro line.\n\n" + ("Sentence about literacy. " * 120) + "\n\nTail.\n"
    chunks = chunk_text(text, target_chars=300)
    assert len(chunks) > 3
    for c in chunks:
        assert text[c.start : c.end] == c.text
        assert len(c.text) <= 600
    assert chunks[-1].text == "Tail."


def test_empty_text_has_no_chunks():
    assert chunk_text("   \n\n  ") == []


def test_lexical_relevance_weights_numbers():
    claim = "literacy rose to 81 percent in 2023"
    assert lexical_relevance(claim, "literacy was 81 percent in 2023") > lexical_relevance(
        claim, "literacy improved over time"
    )
    assert lexical_relevance(claim, "unrelated text about rivers") == 0.0
    assert lexical_relevance("[SPEAKER] said", "anything") == 0.0


def test_terms_drop_stopwords_and_placeholders():
    assert terms("[SPEAKER] said the rate was 81.2 percent") == {"rate", "81.2", "percent"}


@pytest.mark.parametrize(
    ("haystack", "quote", "expected"),
    [
        ("alpha beta gamma", "beta", (6, 10)),
        ("alpha beta\n  gamma", "beta gamma", (6, 18)),  # whitespace-only difference
        ("alpha beta gamma", "beta delta", None),  # paraphrase/fabrication
        ("alpha", "   ", None),
    ],
)
def test_locate_quote(haystack, quote, expected):
    assert locate_quote(haystack, quote) == expected
