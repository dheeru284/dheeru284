"""Ajio adapter. Public product pages (schema.org data), robots.txt-gated. Auto-paused if the site refuses automated access; prefer FEED_<KEY>_URL (affiliate feed) when available."""
from __future__ import annotations

from app.crawlers.public import PublicPageAdapter
from app.crawlers.registry import register


@register
class AjioAdapter(PublicPageAdapter):
    key, name, domain = "ajio", "Ajio", "www.ajio.com"
    search_url = "https://www.ajio.com/search/?text={query}"
    product_url_re = r"/p/(?P<id>\d+_[\w]+|\d+)"
    access_policy = "Public product pages (schema.org data), robots.txt-gated. Auto-paused if the site refuses automated access; prefer FEED_<KEY>_URL (affiliate feed) when available."
