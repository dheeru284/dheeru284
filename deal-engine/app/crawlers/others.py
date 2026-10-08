"""Additional Indian retailers. Same policy as the other public-page adapters: robots.txt-gated,
auto-paused when automated access is refused. URL patterns are best-effort and overridable."""
from __future__ import annotations

from app.crawlers.public import PublicPageAdapter
from app.crawlers.registry import register

_POLICY = ("Public product pages (schema.org data), robots.txt-gated. Auto-paused if the site refuses "
           "automated access; prefer FEED_<KEY>_URL (affiliate feed) when available.")


@register
class MeeshoAdapter(PublicPageAdapter):
    key, name, domain = "meesho", "Meesho", "www.meesho.com"
    search_url = "https://www.meesho.com/search?q={query}"
    product_url_re = r"/p/(?P<id>\w+)"
    access_policy = _POLICY


@register
class VijaySalesAdapter(PublicPageAdapter):
    key, name, domain = "vijay_sales", "Vijay Sales", "www.vijaysales.com"
    search_url = "https://www.vijaysales.com/search-listing?q={query}"
    product_url_re = r"/p/(?P<id>\d+)"
    access_policy = _POLICY


@register
class PepperfryAdapter(PublicPageAdapter):
    key, name, domain = "pepperfry", "Pepperfry", "www.pepperfry.com"
    search_url = "https://www.pepperfry.com/site_product/search?q={query}"
    product_url_re = r"/product/[\w-]+-(?P<id>\d+)\.html"
    access_policy = _POLICY


@register
class IkeaIndiaAdapter(PublicPageAdapter):
    key, name, domain = "ikea", "IKEA India", "www.ikea.com"
    search_url = "https://www.ikea.com/in/en/search/?q={query}"
    product_url_re = r"/in/en/p/[\w-]+-(?P<id>\d{8})/?"
    access_policy = _POLICY


@register
class FirstCryAdapter(PublicPageAdapter):
    key, name, domain = "firstcry", "FirstCry", "www.firstcry.com"
    search_url = "https://www.firstcry.com/search?q={query}"
    product_url_re = r"/(?P<id>\d{5,})/product-detail"
    access_policy = _POLICY


@register
class DecathlonIndiaAdapter(PublicPageAdapter):
    key, name, domain = "decathlon", "Decathlon India", "www.decathlon.in"
    search_url = "https://www.decathlon.in/search?Ntt={query}"
    product_url_re = r"/p/(?P<id>\d+)"
    access_policy = _POLICY
