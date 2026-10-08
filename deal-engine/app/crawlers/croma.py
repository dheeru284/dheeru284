"""Croma adapter. Public product pages (schema.org data), robots.txt-gated. Auto-paused if the site refuses automated access; prefer FEED_<KEY>_URL (affiliate feed) when available."""
from __future__ import annotations

from app.crawlers.public import PublicPageAdapter
from app.crawlers.registry import register


@register
class CromaAdapter(PublicPageAdapter):
    key, name, domain = "croma", "Croma", "www.croma.com"
    search_url = "https://www.croma.com/searchB?q={query}%3Arelevance&text={query}"
    product_url_re = r"/p/(?P<id>\d+)"
    access_policy = "Public product pages (schema.org data), robots.txt-gated. Auto-paused if the site refuses automated access; prefer FEED_<KEY>_URL (affiliate feed) when available."
