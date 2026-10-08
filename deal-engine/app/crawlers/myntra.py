"""Myntra adapter. Public product pages (schema.org data), robots.txt-gated. Auto-paused if the site refuses automated access; prefer FEED_<KEY>_URL (affiliate feed) when available."""
from __future__ import annotations

from app.crawlers.public import PublicPageAdapter
from app.crawlers.registry import register


@register
class MyntraAdapter(PublicPageAdapter):
    key, name, domain = "myntra", "Myntra", "www.myntra.com"
    search_url = "https://www.myntra.com/{query}"
    product_url_re = r"/(?P<id>\d{6,})/buy"
    access_policy = "Public product pages (schema.org data), robots.txt-gated. Auto-paused if the site refuses automated access; prefer FEED_<KEY>_URL (affiliate feed) when available."
