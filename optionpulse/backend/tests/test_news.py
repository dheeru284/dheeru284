from datetime import datetime, timezone

import pytest
from defusedxml import EntitiesForbidden

from optionpulse.news import NewsService, digest, parse_rss, score_headline

GOOGLE = b"""<?xml version="1.0"?><rss version="2.0"><channel><title>x</title>
<item><title>Sensex, Nifty surge as FIIs return - Mint</title><link>https://example.com/a</link>
<pubDate>Wed, 28 Oct 2026 05:10:00 GMT</pubDate><source url="https://livemint.com">Mint</source></item>
<item><title>Brent crude surges 3% on supply fears - Reuters</title><link>https://example.com/b</link>
<pubDate>Wed, 28 Oct 2026 06:00:00 GMT</pubDate><source url="https://reuters.com">Reuters</source></item>
<item><title>RBI keeps repo rate unchanged - Reuters</title><link>https://example.com/c</link>
<pubDate>bad date</pubDate><source url="https://reuters.com">Reuters</source></item>
</channel></rss>"""

ET = b"""<rss version="2.0"><channel><item><title>Nifty slumps as rupee weakens</title>
<link>https://example.com/d</link><pubDate>Wed, 28 Oct 2026 12:00:00 +0530</pubDate></item></channel></rss>"""

BOMB = b"""<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;">]>
<rss><channel><item><title>&lol2;</title></item></channel></rss>"""


def test_parse_google_news():
    items = parse_rss(GOOGLE, "G")
    assert [i.title for i in items][0] == "Sensex, Nifty surge as FIIs return"
    assert items[0].source == "Mint" and items[0].link == "https://example.com/a"
    assert items[0].published == datetime(2026, 10, 28, 5, 10, tzinfo=timezone.utc)
    assert items[2].published is None


def test_parse_economic_times():
    item = parse_rss(ET, "Economic Times")[0]
    assert item.source == "Economic Times" and item.label == "NEGATIVE"


def test_entity_expansion_is_refused():
    with pytest.raises(EntitiesForbidden):
        parse_rss(BOMB, "evil")


@pytest.mark.parametrize("title,label", [
    ("Nifty surges to record high", "POSITIVE"),
    ("Sensex falls 800 points on war fears", "NEGATIVE"),
    ("Brent crude surges 3% on supply cuts", "NEGATIVE"),  # rising oil hurts India
    ("Oil prices fall as OPEC raises output", "POSITIVE"),
    ("India VIX jumps 12%", "NEGATIVE"),
    ("RBI keeps repo rate unchanged", "NEUTRAL"),
    ("Fed signals rate cut, markets cheer", "POSITIVE"),
])
def test_headline_scores(title, label):
    assert score_headline(title)[1] == label


def test_topics():
    assert "Crude oil" in score_headline("Brent crude surges")[2]
    assert "RBI / rates" in score_headline("RBI policy today")[2]


def test_digest_dedupes_and_scores():
    items = parse_rss(GOOGLE, "G") + parse_rss(GOOGLE, "G2") + parse_rss(ET, "ET")
    d = digest(items, [], datetime.now(timezone.utc))
    assert len(d.items) == 4
    assert d.items[0].title.startswith("Nifty slumps")  # newest first
    assert d.positive == 1 and d.negative == 2 and d.neutral == 1
    assert d.mood is not None and -1 <= d.mood <= 1


def test_service_isolates_feed_failures_and_caches():
    calls = []

    def fetch(url):
        calls.append(url)
        if url == "bad":
            raise ConnectionError("blocked")
        return GOOGLE

    svc = NewsService(feeds=(("ok", "good"), ("broken", "bad")), fetch=fetch)
    d = svc.latest()
    assert len(d.items) == 3 and d.errors and "broken" in d.errors[0]
    svc.latest()
    assert len(calls) == 2  # second call served from cache
