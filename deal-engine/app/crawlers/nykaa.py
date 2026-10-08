"""Nykaa adapter. Public product pages (schema.org data), robots.txt-gated. Auto-paused if the site refuses automated access; prefer FEED_<KEY>_URL (affiliate feed) when available."""
from __future__ import annotations

from app.crawlers.public import PublicPageAdapter
from app.crawlers.registry import register


@register
class NykaaAdapter(PublicPageAdapter):
    key, name, domain = "nykaa", "Nykaa", "www.nykaa.com"
    search_url = "https://www.nykaa.com/search/result/?q={query}"
    product_url_re = r"/p/(?P<id>\d+)"
    access_policy = "Public product pages (schema.org data), robots.txt-gated. Auto-paused if the site refuses automated access; prefer FEED_<KEY>_URL (affiliate feed) when available."
