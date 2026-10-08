"""Polite HTTP/browser fetching: robots.txt, per-domain throttling, caching, block detection.

Nothing here tries to disguise the client or defeat bot protection. If a site says no
(robots.txt, 403/429, CAPTCHA, login wall) we raise RetailerBlocked and stop."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from app.config.settings import Settings, get_settings
from app.crawlers.base import RetailerBlocked, RetailerError
from app.utils.logging import get_logger

log = get_logger(__name__)

BLOCK_MARKERS = (
    "captcha", "robot check", "are you a human", "unusual traffic", "automated access",
    "access denied", "verify you are human", "bot detection", "enter the characters you see",
)


@dataclass
class FetchResult:
    url: str
    status: int
    text: str
    duration_ms: int
    from_cache: bool = False


def looks_blocked(status: int, text: str) -> bool:
    if status in (401, 403, 429, 451):
        return True
    head = text[:6000].lower()
    return status >= 400 and any(m in head for m in BLOCK_MARKERS) or (
        status == 200 and len(text) < 20000 and any(m in head for m in BLOCK_MARKERS)
    )


class _Cache:
    """Redis-backed response cache with in-process fallback."""

    def __init__(self, settings: Settings):
        self.ttl = settings.page_cache_ttl_seconds
        self._mem: dict[str, tuple[float, str]] = {}
        self._redis = None
        try:
            import redis

            r = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1, decode_responses=True)
            r.ping()
            self._redis = r
        except Exception:
            self._redis = None

    def get(self, key: str) -> str | None:
        if self.ttl <= 0:
            return None
        if self._redis is not None:
            try:
                return self._redis.get(f"page:{key}")  # type: ignore[return-value]
            except Exception:
                pass
        hit = self._mem.get(key)
        return hit[1] if hit and time.monotonic() - hit[0] < self.ttl else None

    def set(self, key: str, value: str) -> None:
        if self.ttl <= 0:
            return
        if self._redis is not None:
            try:
                self._redis.set(f"page:{key}", value, ex=self.ttl)
                return
            except Exception:
                pass
        self._mem[key] = (time.monotonic(), value)


class Throttle:
    """Minimum interval between requests per domain (cross-process via Redis when available)."""

    def __init__(self, interval: float, redis_client=None):  # type: ignore[no-untyped-def]
        self.interval = interval
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()
        self._redis = redis_client

    def wait(self, domain: str) -> None:
        if self.interval <= 0:
            return
        if self._redis is not None:
            try:
                for _ in range(600):
                    if self._redis.set(f"throttle:{domain}", 1, nx=True, px=int(self.interval * 1000)):
                        return
                    time.sleep(0.25)
                return
            except Exception:
                pass
        with self._lock:
            delay = self._last.get(domain, 0) + self.interval - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            self._last[domain] = time.monotonic()


class RobotsCache:
    def __init__(self, user_agent: str, client: httpx.Client, ttl: float = 86400):
        self.ua, self.client, self.ttl = user_agent, client, ttl
        self._cache: dict[str, tuple[float, RobotFileParser | None, list[str]]] = {}

    def _load(self, origin: str) -> tuple[RobotFileParser | None, list[str]]:
        hit = self._cache.get(origin)
        if hit and time.monotonic() - hit[0] < self.ttl:
            return hit[1], hit[2]
        parser: RobotFileParser | None = RobotFileParser()
        sitemaps: list[str] = []
        try:
            r = self.client.get(f"{origin}/robots.txt", timeout=10)
            if r.status_code == 200:
                lines = r.text.splitlines()
                parser.parse(lines)  # type: ignore[union-attr]
                sitemaps = [ln.split(":", 1)[1].strip() for ln in lines if ln.lower().startswith("sitemap:")]
            elif r.status_code in (401, 403) or r.status_code >= 500:
                parser.disallow_all = True  # type: ignore[union-attr]
            else:  # 404 & friends: no robots.txt -> allowed
                parser.allow_all = True  # type: ignore[union-attr]
        except httpx.HTTPError:
            parser = None  # unknown -> be conservative (disallow)
        self._cache[origin] = (time.monotonic(), parser, sitemaps)
        return parser, sitemaps

    def allowed(self, url: str) -> bool:
        p = urlparse(url)
        parser, _ = self._load(f"{p.scheme}://{p.netloc}")
        return bool(parser and parser.can_fetch(self.ua, url))

    def sitemaps(self, url: str) -> list[str]:
        p = urlparse(url)
        return self._load(f"{p.scheme}://{p.netloc}")[1]


class Fetcher:
    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None):
        self.s = settings or get_settings()
        self.client = client or httpx.Client(
            headers={"User-Agent": self.s.user_agent, "Accept-Language": "en-IN,en;q=0.9",
                     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
            follow_redirects=True, timeout=self.s.http_timeout_seconds,
        )
        self.cache = _Cache(self.s)
        self.throttle = Throttle(self.s.per_domain_min_interval_seconds, self.cache._redis)
        self.robots = RobotsCache(self.s.user_agent, self.client)

    def check_allowed(self, url: str) -> None:
        if self.s.respect_robots and not self.robots.allowed(url):
            raise RetailerBlocked(f"robots.txt disallows fetching {urlparse(url).path}")

    def get(self, url: str, use_cache: bool = True) -> FetchResult:
        self.check_allowed(url)
        if use_cache and (cached := self.cache.get(url)) is not None:
            return FetchResult(url, 200, cached, 0, True)
        self.throttle.wait(urlparse(url).netloc)
        started = time.monotonic()
        try:
            resp = self.client.get(url)
        except httpx.HTTPError as exc:
            raise RetailerError(f"network error: {exc.__class__.__name__}: {exc}") from exc
        ms = int((time.monotonic() - started) * 1000)
        if looks_blocked(resp.status_code, resp.text):
            raise RetailerBlocked(f"blocked: HTTP {resp.status_code} (automated access refused)")
        if resp.status_code == 404:
            from app.crawlers.base import ProductNotFound

            raise ProductNotFound(url)
        if resp.status_code >= 400:
            raise RetailerError(f"HTTP {resp.status_code}")
        if use_cache:
            self.cache.set(url, resp.text)
        return FetchResult(url, resp.status_code, resp.text, ms)


class BrowserFetcher(Fetcher):
    """Playwright rendering for JS-only pages, only where robots.txt/ToS permit.
    Standard browser context (locale/timezone/viewport); no stealth, fingerprint spoofing or
    CAPTCHA handling. Screenshots are saved on failure for debugging."""

    def get(self, url: str, use_cache: bool = True) -> FetchResult:
        self.check_allowed(url)
        if use_cache and (cached := self.cache.get(url)) is not None:
            return FetchResult(url, 200, cached, 0, True)
        try:
            from playwright.sync_api import Error as PwError
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover
            raise RetailerError("playwright is not installed") from exc
        self.throttle.wait(urlparse(url).netloc)
        started = time.monotonic()
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent=self.s.user_agent, locale="en-IN", timezone_id="Asia/Kolkata",
                viewport={"width": 1366, "height": 768},
            )
            page = ctx.new_page()
            page.set_default_timeout(self.s.http_timeout_seconds * 1000)
            try:
                resp = page.goto(url, wait_until="domcontentloaded")
                page.wait_for_load_state("networkidle", timeout=8000)
                html = page.content()
                status = resp.status if resp else 0
            except PwError as exc:
                self._screenshot(page, url)
                raise RetailerError(f"browser error: {exc}") from exc
            finally:
                browser.close()
        ms = int((time.monotonic() - started) * 1000)
        if looks_blocked(status, html):
            raise RetailerBlocked(f"blocked: HTTP {status} (automated access refused)")
        if status >= 400:
            raise RetailerError(f"HTTP {status}")
        if use_cache:
            self.cache.set(url, html)
        return FetchResult(url, status, html, ms)

    def _screenshot(self, page, url: str) -> None:  # type: ignore[no-untyped-def]
        try:
            d = Path(self.s.debug_dir)
            d.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(d / f"{urlparse(url).netloc}-{int(time.time())}.png"))
        except Exception:
            pass


def get_fetcher(settings: Settings | None = None, browser: bool = False) -> Fetcher:
    s = settings or get_settings()
    return BrowserFetcher(s) if (browser and s.browser_enabled) else Fetcher(s)
