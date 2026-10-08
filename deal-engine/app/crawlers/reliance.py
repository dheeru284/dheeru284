"""Reliance Digital adapter. Public product pages (schema.org data), robots.txt-gated. Auto-paused if the site refuses automated access; prefer FEED_<KEY>_URL (affiliate feed) when available."""
from __future__ import annotations

from app.crawlers.public import PublicPageAdapter
from app.crawlers.registry import register


@register
class RelianceDigitalAdapter(PublicPageAdapter):
    key, name, domain = "reliance_digital", "Reliance Digital", "www.reliancedigital.in"
    search_url = "https://www.reliancedigital.in/products?q={query}"
    product_url_re = r"/p/(?P<id>\d+)"
    access_policy = "Public product pages (schema.org data), robots.txt-gated. Auto-paused if the site refuses automated access; prefer FEED_<KEY>_URL (affiliate feed) when available."
