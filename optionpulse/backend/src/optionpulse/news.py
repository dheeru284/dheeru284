"""Market headlines from public RSS feeds, with a transparent keyword score.

The score is a lexicon count, not a language model: each headline gets
+1 per positive word and -1 per negative word, normalised to [-1, 1].
Direction words ("surges", "falls") flip sign when the headline is about
something that hurts NIFTY when it rises (crude oil, VIX, US yields, the
dollar), so "Brent surges 3%" scores negative for Indian equities.

News is shown as context only. It is not fed into the paper-trading engine,
because there is no archive of past headlines to test such a rule against.
"""

from __future__ import annotations

import re
import threading
import time as _time
from collections.abc import Callable
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx
from defusedxml import ElementTree
from pydantic import BaseModel

from .providers.yahoo import USER_AGENT

FEEDS: tuple[tuple[str, str], ...] = (
    ("Google News · Indian markets",
     "https://news.google.com/rss/search?q=(nifty+OR+sensex+OR+%22indian+stock+market%22)+when:1d&hl=en-IN&gl=IN&ceid=IN:en"),
    ("Google News · crude & rupee",
     "https://news.google.com/rss/search?q=(crude+oil+OR+brent+OR+rupee)+india+when:1d&hl=en-IN&gl=IN&ceid=IN:en"),
    ("Economic Times · Markets", "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"),
)

DIRECTION_UP = {
    "rise", "rises", "rising", "rose", "surge", "surges", "surged", "jump", "jumps", "jumped", "gain", "gains",
    "gained", "climb", "climbs", "climbed", "soar", "soars", "soared", "rally", "rallies", "rallied",
    "rebound", "rebounds", "rebounded", "higher", "up", "spikes", "spike", "spiked",
}
DIRECTION_DOWN = {
    "fall", "falls", "falling", "fell", "drop", "drops", "dropped", "slump", "slumps", "slumped", "plunge",
    "plunges", "plunged", "decline", "declines", "declined", "slide", "slides", "slid", "tumble", "tumbles",
    "tumbled", "sink", "sinks", "sank", "lower", "down", "eases", "ease", "eased", "cools", "cooled", "dips", "dip",
}
POSITIVE = {
    "record", "upbeat", "beat", "beats", "upgrade", "upgrades", "bullish", "inflows", "boost", "boosts",
    "recovery", "recovers", "optimism", "strong", "robust", "outperform", "buying", "relief",
}
NEGATIVE = {
    "crash", "crashes", "selloff", "sell-off", "outflows", "downgrade", "downgrades", "miss", "misses",
    "bearish", "fear", "fears", "war", "tension", "tensions", "tariff", "tariffs", "sanctions", "recession",
    "inflation", "hike", "hikes", "weak", "weakens", "worries", "worry", "concern", "concerns", "losses",
    "selling", "volatile", "slowdown", "default", "attack", "conflict",
}
RATE_CUT = {"cut", "cuts"}
RATE_WORDS = {"rate", "rates", "repo", "rbi", "fed", "fomc"}
# Topics where a *rise* is bad for Indian equities.
INVERTING_TOPICS = {"Crude oil", "Volatility", "US yields", "Dollar"}
TOPICS: dict[str, set[str]] = {
    "Crude oil": {"crude", "oil", "brent", "opec", "wti"},
    "Volatility": {"vix"},
    "US yields": {"yield", "yields", "treasury", "treasuries"},
    "Dollar": {"dollar", "dxy"},
    "Rupee": {"rupee", "inr"},
    "RBI / rates": {"rbi", "repo", "mpc"},
    "US Fed": {"fed", "powell", "fomc"},
    "FII flows": {"fii", "fiis", "fpi", "fpis", "inflows", "outflows"},
    "Earnings": {"earnings", "q1", "q2", "q3", "q4", "profit", "results"},
    "Geopolitics": {"war", "tariff", "tariffs", "sanctions", "conflict", "attack", "tension", "tensions"},
    "Inflation": {"inflation", "cpi", "wpi"},
}
_WORD = re.compile(r"[a-z0-9][a-z0-9\-]*")


class NewsItem(BaseModel):
    title: str
    link: str
    source: str
    feed: str
    published: datetime | None
    score: float
    label: str  # POSITIVE / NEGATIVE / NEUTRAL
    topics: list[str]
    matched: list[str]


class NewsDigest(BaseModel):
    items: list[NewsItem]
    mood: float | None
    positive: int
    negative: int
    neutral: int
    errors: list[str]
    fetched_at: datetime


def score_headline(title: str) -> tuple[float, str, list[str], list[str]]:
    words = _WORD.findall(title.lower())
    wordset = set(words)
    topics = [t for t, keys in TOPICS.items() if wordset & keys]
    invert = any(t in INVERTING_TOPICS for t in topics)
    total, matched = 0, []
    for w in words:
        if w in DIRECTION_UP or w in DIRECTION_DOWN:
            sign = 1 if w in DIRECTION_UP else -1
            total += -sign if invert else sign
            matched.append(w)
        elif w in RATE_CUT and wordset & RATE_WORDS:
            total += 1  # "rate cut" is good for equities; "supply cuts" or "job cuts" are not
            matched.append(w)
        elif w in POSITIVE:
            total += 1
            matched.append(w)
        elif w in NEGATIVE:
            total -= 1
            matched.append(w)
    score = max(-1.0, min(1.0, total / max(1, len(matched)))) if matched else 0.0
    label = "POSITIVE" if score > 0.2 else "NEGATIVE" if score < -0.2 else "NEUTRAL"
    return score, label, topics, matched


def _text(el, tag: str) -> str:
    child = el.find(tag)
    return (child.text or "").strip() if child is not None and child.text else ""


def parse_rss(xml: bytes, feed_name: str) -> list[NewsItem]:
    root = ElementTree.fromstring(xml)
    items = []
    for item in root.iter("item"):
        title = _text(item, "title")
        if not title:
            continue
        source = _text(item, "source")
        if source and title.endswith(f" - {source}"):
            title = title[: -len(source) - 3].rstrip()
        published = None
        if raw := _text(item, "pubDate"):
            try:
                published = parsedate_to_datetime(raw)
                if published.tzinfo is None:
                    published = published.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                published = None
        score, label, topics, matched = score_headline(title)
        items.append(NewsItem(
            title=title, link=_text(item, "link"), source=source or feed_name, feed=feed_name,
            published=published, score=score, label=label, topics=topics, matched=matched,
        ))
    return items


def digest(items: list[NewsItem], errors: list[str], fetched_at: datetime, limit: int = 40) -> NewsDigest:
    seen, unique = set(), []
    for it in sorted(items, key=lambda i: i.published or datetime.min.replace(tzinfo=timezone.utc), reverse=True):
        key = re.sub(r"\W+", "", it.title.lower())[:80]
        if key not in seen:
            seen.add(key)
            unique.append(it)
    unique = unique[:limit]
    scored = [i.score for i in unique if i.label != "NEUTRAL"]
    return NewsDigest(
        items=unique,
        mood=sum(scored) / len(scored) if scored else None,
        positive=sum(i.label == "POSITIVE" for i in unique),
        negative=sum(i.label == "NEGATIVE" for i in unique),
        neutral=sum(i.label == "NEUTRAL" for i in unique),
        errors=errors,
        fetched_at=fetched_at,
    )


class NewsService:
    def __init__(
        self,
        feeds: tuple[tuple[str, str], ...] = FEEDS,
        fetch: Callable[[str], bytes] | None = None,
        ttl_seconds: float = 300.0,
    ) -> None:
        self.feeds = feeds
        self._fetch = fetch or self._http_fetch
        self._ttl = ttl_seconds
        self._cached: tuple[float, NewsDigest] | None = None
        self._lock = threading.Lock()
        self._http: httpx.Client | None = None

    def _http_fetch(self, url: str) -> bytes:
        if self._http is None:
            self._http = httpx.Client(timeout=8.0, headers={"User-Agent": USER_AGENT}, follow_redirects=True)
        resp = self._http.get(url)
        resp.raise_for_status()
        return resp.content

    def latest(self) -> NewsDigest:
        now = _time.time()
        with self._lock:
            if self._cached and self._cached[0] > now:
                return self._cached[1]
        items, errors = [], []
        for name, url in self.feeds:
            try:
                items.extend(parse_rss(self._fetch(url), name))
            except Exception as exc:  # one bad feed must not hide the others
                errors.append(f"{name}: {type(exc).__name__}: {exc}"[:200])
        result = digest(items, errors, datetime.now(timezone.utc))
        with self._lock:
            # Cache failures briefly so a dead network is not hammered every request.
            self._cached = (now + (self._ttl if items else 60.0), result)
        return result
