"""Adapter for permitted product feeds (affiliate-network CSV/JSON feeds, retailer data feeds).

Set FEED_<RETAILER_KEY>_URL (https URL or local file path). Supported formats: CSV, JSON array,
JSON lines. Default column names are listed in FIELD_MAP; override with FEED_<KEY>_MAP='{"price":"sale_price"}'."""
from __future__ import annotations

import csv
import io
import json
import os
import time
from pathlib import Path

import httpx

from app.config.settings import Settings, get_settings
from app.crawlers.base import (
    ProductCandidate,
    ProductNotFound,
    RetailerAdapter,
    RetailerNotConfigured,
    ScrapedProduct,
)
from app.utils.normalization import parse_price

FIELD_MAP = {
    "id": "id", "url": "url", "title": "title", "brand": "brand", "price": "price", "currency": "currency",
    "mrp": "mrp", "rating": "rating", "review_count": "review_count", "in_stock": "in_stock",
    "gtin": "gtin", "mpn": "mpn", "category": "category", "seller": "seller", "image_url": "image_url",
}
_feed_cache: dict[str, tuple[float, dict[str, ScrapedProduct]]] = {}


def _truthy(v) -> bool:  # type: ignore[no-untyped-def]
    return str(v).strip().lower() in ("1", "true", "yes", "y", "in stock", "instock", "available")


def parse_feed(text: str, mapping: dict[str, str], default_currency: str = "INR") -> list[ScrapedProduct]:
    text = text.strip()
    rows: list[dict]
    if text.startswith("["):
        rows = json.loads(text)
    elif text.startswith("{"):
        rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    else:
        rows = list(csv.DictReader(io.StringIO(text)))
    out = []
    for r in rows:
        def g(k: str, r: dict = r):  # type: ignore[no-untyped-def]
            return r.get(mapping.get(k, k))

        price, pid, url, title = parse_price(g("price")), g("id"), g("url"), g("title")
        if price is None or not pid or not url or not title:
            continue
        stock = g("in_stock")
        out.append(ScrapedProduct(
            retailer_product_id=str(pid), url=str(url), title=str(title), price=price,
            currency=(g("currency") or default_currency).upper(), in_stock=_truthy(stock) if stock is not None else True,
            rating=parse_price(g("rating")), review_count=int(parse_price(g("review_count")) or 0) or None,
            brand=g("brand"), mpn=g("mpn"), gtin=g("gtin"), category=g("category"), seller=g("seller"),
            image_url=g("image_url"), mrp=parse_price(g("mrp")),
        ))
    return out


class FeedAdapter(RetailerAdapter):
    access_policy = "Reads a permitted product feed configured via FEED_<KEY>_URL."

    def __init__(self, base: type[RetailerAdapter] | RetailerAdapter, settings: Settings | None = None):
        self.s = settings or get_settings()
        self.key, self.name, self.domain = base.key, base.name, base.domain
        self.country, self.currency = base.country, base.currency
        env = f"FEED_{self.key.upper()}_URL"
        self.source = os.environ.get(env)
        mp = os.environ.get(f"FEED_{self.key.upper()}_MAP")
        self.mapping = {**FIELD_MAP, **(json.loads(mp) if mp else {})}

    def is_configured(self) -> bool:
        return bool(self.source)

    def _load(self) -> dict[str, ScrapedProduct]:
        if not self.source:
            raise RetailerNotConfigured(f"FEED_{self.key.upper()}_URL not set")
        hit = _feed_cache.get(self.source)
        if hit and time.monotonic() - hit[0] < 3600:
            return hit[1]
        if self.source.startswith("http"):
            r = httpx.get(self.source, timeout=60, follow_redirects=True, headers={"User-Agent": self.s.user_agent})
            r.raise_for_status()
            text = r.text
        else:
            text = Path(self.source).read_text(encoding="utf-8")
        items = {p.retailer_product_id: p for p in parse_feed(text, self.mapping, self.currency)}
        _feed_cache[self.source] = (time.monotonic(), items)
        return items

    def search_products(self, query: str, limit: int = 20) -> list[ProductCandidate]:
        q = query.lower().split()
        hits = [p for p in self._load().values() if all(w in (p.title or "").lower() for w in q)]
        return [ProductCandidate(p.retailer_product_id, p.url, p.title, p.category, p) for p in hits[:limit]]

    def discover_products(self, queries, limit_per_query=20, max_queries=40):  # type: ignore[no-untyped-def]
        return [(p.category or "uncategorized", ProductCandidate(p.retailer_product_id, p.url, p.title, p.category, p))
                for p in list(self._load().values())[: limit_per_query * max_queries]]

    def fetch_product(self, url_or_id: str) -> ScrapedProduct:
        items = self._load()
        if url_or_id in items:
            return items[url_or_id]
        for p in items.values():
            if p.url == url_or_id:
                return p
        raise ProductNotFound(url_or_id)
