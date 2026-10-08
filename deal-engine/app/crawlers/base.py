"""Retailer adapter interface. All retailer-specific logic lives behind this class."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class RetailerError(Exception):
    """Base for adapter failures."""


class RetailerBlocked(RetailerError):
    """Retailer refuses automated access (robots.txt, 403/429, CAPTCHA, login wall).
    We never try to get around this; the retailer is paused and the system moves on."""


class RetailerNotConfigured(RetailerError):
    """Required API credentials / feed are missing."""


class ParseError(RetailerError):
    """Page/API response did not contain the expected product data."""


class ProductNotFound(RetailerError):
    pass


@dataclass
class ScrapedProduct:
    retailer_product_id: str
    url: str
    title: str
    price: float | None  # payable listing price, original currency
    currency: str = "INR"
    in_stock: bool = True
    rating: float | None = None
    review_count: int | None = None
    brand: str | None = None
    model: str | None = None
    mpn: str | None = None
    gtin: str | None = None
    category: str | None = None
    seller: str | None = None
    variant: str | None = None
    image_url: str | None = None
    mrp: float | None = None  # informational only
    shipping_cost: float = 0.0
    coupon_discount: float | None = None
    coupon_verified: bool = False
    membership_price: float | None = None
    payable: bool = True  # False for EMI-only / subscription-only prices
    condition: str | None = None  # None/"new" | "refurbished" | "used"
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProductCandidate:
    retailer_product_id: str
    url: str
    title: str | None = None
    category: str | None = None
    prefetched: ScrapedProduct | None = None  # APIs/feeds return full data during discovery


class RetailerAdapter(ABC):
    key: str
    name: str
    domain: str
    country: str = "IN"
    currency: str = "INR"
    #: Human-readable access policy / limitation, surfaced in the README and /retailers.
    access_policy: str = ""

    def is_configured(self) -> bool:
        return True

    @abstractmethod
    def search_products(self, query: str, limit: int = 20) -> list[ProductCandidate]: ...

    @abstractmethod
    def fetch_product(self, url_or_id: str) -> ScrapedProduct: ...

    def discover_products(self, queries: dict[str, list[str]], limit_per_query: int = 20,
                          max_queries: int = 40) -> list[tuple[str, ProductCandidate]]:
        """Default discovery: run category keywords through search. Returns (category, candidate)."""
        out: list[tuple[str, ProductCandidate]] = []
        n = 0
        for category, keywords in queries.items():
            for kw in keywords:
                if n >= max_queries:
                    return out
                n += 1
                for cand in self.search_products(kw, limit_per_query):
                    cand.category = cand.category or category
                    out.append((category, cand))
        return out

    def fetch_listing(self, retailer_product_id: str, url: str) -> ScrapedProduct:
        """Refresh a known listing. Override when the API is keyed by id rather than URL."""
        return self.fetch_product(url)

    # Convenience accessors; adapters with cheaper dedicated endpoints can override them.
    def fetch_price(self, url_or_id: str) -> tuple[float | None, str]:
        p = self.fetch_product(url_or_id)
        return p.price, p.currency

    def fetch_rating(self, url_or_id: str) -> tuple[float | None, int | None]:
        p = self.fetch_product(url_or_id)
        return p.rating, p.review_count

    def fetch_availability(self, url_or_id: str) -> bool:
        return self.fetch_product(url_or_id).in_stock

    def fetch_reviews(self, url_or_id: str, limit: int = 20) -> list[dict[str, Any]]:
        """Individual reviews are not collected by default (only aggregate rating + count)."""
        return []
