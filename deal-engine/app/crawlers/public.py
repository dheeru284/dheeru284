"""Generic adapter for retailers that publish schema.org product data on public pages.

Fetching is gated by robots.txt and block detection. Where a retailer disallows search pages
(common), discovery falls back to sitemaps and curated URLs (config/seed_urls.yaml)."""
from __future__ import annotations

import re
from urllib.parse import quote_plus, urlparse

from app.config.settings import Settings, get_settings
from app.crawlers.base import (
    ParseError,
    ProductCandidate,
    RetailerAdapter,
    RetailerBlocked,
    ScrapedProduct,
)
from app.crawlers.http import Fetcher, get_fetcher
from app.crawlers.parsers import extract_links, parse_product_page, parse_sitemap
from app.utils.logging import get_logger

log = get_logger(__name__)


class PublicPageAdapter(RetailerAdapter):
    #: URL template with {query}; None if the site has no usable public search.
    search_url: str | None = None
    #: regex matching product page URLs; group "id" (or group 1) is the retailer product id.
    product_url_re: str = r"/p/(?P<id>[A-Za-z0-9_-]+)"
    scheme: str = "https"
    use_browser: bool = False  # render with Playwright (only if BROWSER_ENABLED and permitted)
    sitemap_max_urls: int = 200

    def __init__(self, settings: Settings | None = None, fetcher: Fetcher | None = None):
        self.s = settings or get_settings()
        self._fetcher = fetcher

    @property
    def fetcher(self) -> Fetcher:
        if self._fetcher is None:
            self._fetcher = get_fetcher(self.s, browser=self.use_browser)
        return self._fetcher

    @property
    def _pattern(self) -> re.Pattern[str]:
        return re.compile(self.product_url_re)

    def product_id_from_url(self, url: str) -> str | None:
        m = self._pattern.search(urlparse(url).path)
        if not m:
            return None
        return m.groupdict().get("id") or (m.group(1) if m.groups() else None)

    def candidate_from_url(self, url: str) -> ProductCandidate | None:
        pid = self.product_id_from_url(url)
        return ProductCandidate(pid, url) if pid else None

    def search_products(self, query: str, limit: int = 20) -> list[ProductCandidate]:
        if not self.search_url:
            return []
        url = self.search_url.format(query=quote_plus(query))
        try:
            res = self.fetcher.get(url)
        except RetailerBlocked as exc:
            # robots.txt commonly disallows search pages: not an outage, just not permitted.
            if "robots.txt" in str(exc):
                log.info("search not permitted by robots.txt", extra={"retailer": self.key, "url": url})
                return []
            raise
        out = []
        for link in extract_links(res.text, url, self._pattern, limit):
            cand = self.candidate_from_url(link)
            if cand:
                out.append(cand)
        return out[:limit]

    def discover_from_sitemaps(self, limit: int = 200) -> list[ProductCandidate]:
        base = f"{self.scheme}://{self.domain}/"
        pending = list(self.fetcher.robots.sitemaps(base))
        out: list[ProductCandidate] = []
        seen = 0
        while pending and len(out) < limit and seen < 20:
            sm = pending.pop(0)
            seen += 1
            try:
                res = self.fetcher.get(sm)
            except Exception as exc:
                log.info("sitemap skipped", extra={"retailer": self.key, "url": sm, "error": str(exc)})
                continue
            children, pages = parse_sitemap(res.text)
            pending.extend(children)
            for page in pages:
                cand = self.candidate_from_url(page)
                if cand:
                    out.append(cand)
                    if len(out) >= limit:
                        break
        return out

    def fetch_product(self, url_or_id: str) -> ScrapedProduct:
        url = url_or_id
        if not url.startswith("http"):
            raise ParseError("public-page adapters need a product URL")
        res = self.fetcher.get(url)
        return parse_product_page(res.text, url, self.product_id_from_url(url))
