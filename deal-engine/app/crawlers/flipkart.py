"""Flipkart via the official Flipkart Affiliate API (needs FLIPKART_AFFILIATE_ID / _TOKEN).

NOTE: written from the public Affiliate API v1.0 documentation (search.json / product.json); the
v1 payload has no ratings, so ratings come from other matched retailers. Not exercised against live
credentials in this repository's test-suite. If you have a Flipkart product feed, FEED_FLIPKART_URL
takes precedence."""
from __future__ import annotations

import httpx

from app.config.settings import Settings, get_settings
from app.crawlers.base import (
    ParseError,
    ProductCandidate,
    ProductNotFound,
    RetailerAdapter,
    RetailerBlocked,
    RetailerError,
    RetailerNotConfigured,
    ScrapedProduct,
)
from app.crawlers.registry import register

API = "https://affiliate-api.flipkart.net/affiliate/1.0"


@register
class FlipkartAdapter(RetailerAdapter):
    key, name, domain = "flipkart", "Flipkart", "www.flipkart.com"
    access_policy = "Official Affiliate API (FLIPKART_AFFILIATE_ID/TOKEN) or a permitted feed. No scraping."

    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None):
        self.s = settings or get_settings()
        self.client = client or httpx.Client(timeout=self.s.http_timeout_seconds)

    def is_configured(self) -> bool:
        return bool(self.s.flipkart_affiliate_id and self.s.flipkart_affiliate_token)

    def _get(self, path: str, params: dict) -> dict:
        if not self.is_configured():
            raise RetailerNotConfigured("FLIPKART_AFFILIATE_ID / FLIPKART_AFFILIATE_TOKEN not set")
        r = self.client.get(f"{API}/{path}", params=params, headers={
            "Fk-Affiliate-Id": str(self.s.flipkart_affiliate_id), "Fk-Affiliate-Token": str(self.s.flipkart_affiliate_token),
        })
        if r.status_code in (401, 403):
            raise RetailerBlocked(f"Flipkart API rejected credentials: HTTP {r.status_code}")
        if r.status_code == 429:
            raise RetailerBlocked("Flipkart API rate limit (HTTP 429)")
        if r.status_code == 404:
            raise ProductNotFound(str(params))
        if r.status_code >= 400:
            raise RetailerError(f"Flipkart API HTTP {r.status_code}")
        return r.json()

    @staticmethod
    def _to_product(base: dict) -> ScrapedProduct:
        price = (base.get("flipkartSpecialPrice") or base.get("flipkartSellingPrice") or {})
        mrp = (base.get("maximumRetailPrice") or {}).get("amount")
        if not base.get("title") or price.get("amount") is None:
            raise ParseError("Flipkart item without title/price")
        return ScrapedProduct(
            retailer_product_id=base["productId"], url=base["productUrl"], title=base["title"],
            price=float(price["amount"]), currency=price.get("currency", "INR"),
            in_stock=bool(base.get("inStock", True)), brand=base.get("productBrand"),
            category=(base.get("categoryPath") or "").split(">")[0].strip() or None,
            mrp=float(mrp) if mrp else None, seller="Flipkart marketplace",
            image_url=next(iter((base.get("imageUrls") or {}).values()), None),
        )

    def search_products(self, query: str, limit: int = 10) -> list[ProductCandidate]:
        data = self._get("search.json", {"query": query, "resultCount": min(limit, 10)})
        out = []
        for item in data.get("products", []):
            try:
                p = self._to_product(item["productBaseInfoV1"])
            except (ParseError, KeyError):
                continue
            out.append(ProductCandidate(p.retailer_product_id, p.url, p.title, p.category, p))
        return out

    def fetch_product(self, url_or_id: str) -> ScrapedProduct:
        data = self._get("product.json", {"id": url_or_id})
        return self._to_product(data["productBaseInfoV1"])

    def fetch_listing(self, retailer_product_id: str, url: str) -> ScrapedProduct:
        return self.fetch_product(retailer_product_id)
