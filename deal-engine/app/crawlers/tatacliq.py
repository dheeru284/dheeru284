"""Tata CLiQ adapter. Public product pages (schema.org data), robots.txt-gated. Auto-paused if the site refuses automated access; prefer FEED_<KEY>_URL (affiliate feed) when available."""
from __future__ import annotations

from app.crawlers.public import PublicPageAdapter
from app.crawlers.registry import register


@register
class TataCliqAdapter(PublicPageAdapter):
    key, name, domain = "tata_cliq", "Tata CLiQ", "www.tatacliq.com"
    search_url = "https://www.tatacliq.com/search/?searchCategory=all&text={query}"
    product_url_re = r"/p-(?P<id>mp\d+)"
    access_policy = "Public product pages (schema.org data), robots.txt-gated. Auto-paused if the site refuses automated access; prefer FEED_<KEY>_URL (affiliate feed) when available."
