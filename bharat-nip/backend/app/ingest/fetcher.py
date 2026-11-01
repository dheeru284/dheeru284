"""Outbound HTTP fetching with SSRF protection (SECURITY.md §2).

- scheme allowlist (https; http only if BNIP_FETCH_ALLOW_HTTP)
- every hop's hostname is resolved, and private / loopback / link-local / multicast /
  reserved addresses are refused
- redirects are followed manually (max 5) so each hop is re-validated
- response size and time are bounded

Known limitation: the check resolves DNS before httpx connects, so a DNS-rebinding
attacker controlling a hostname could race it. Production deployments should also
route fetches through an egress proxy that enforces the same policy.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import urljoin, urlsplit

import httpx

from app.core.config import Settings

MAX_REDIRECTS = 5
Resolver = Callable[[str], list[str]]


class FetchError(Exception):
    pass


class BlockedURL(FetchError):
    pass


@dataclass(frozen=True)
class FetchedDocument:
    requested_url: str
    final_url: str
    status_code: int
    content_type: str
    body: bytes
    fetched_at: datetime
    redirects: list[str] = field(default_factory=list)


def _default_resolver(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise FetchError(f"Cannot resolve host '{host}': {exc}") from exc
    return sorted({info[4][0] for info in infos})


def _is_public(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


class SafeFetcher:
    def __init__(
        self,
        settings: Settings,
        transport: httpx.BaseTransport | None = None,
        resolver: Resolver = _default_resolver,
    ) -> None:
        self.settings = settings
        self.resolver = resolver
        self.allowed_schemes = {"https", "http"} if settings.fetch_allow_http else {"https"}
        self._client = httpx.Client(
            timeout=settings.fetch_timeout_seconds,
            follow_redirects=False,
            transport=transport,
            headers={"User-Agent": settings.fetch_user_agent},
        )

    def validate_url(self, url: str) -> None:
        parts = urlsplit(url)
        if parts.scheme not in self.allowed_schemes:
            raise BlockedURL(f"Scheme '{parts.scheme}' is not allowed.")
        if not parts.hostname:
            raise BlockedURL("URL has no host.")
        if parts.username or parts.password:
            raise BlockedURL("URLs with credentials are not allowed.")
        host = parts.hostname
        try:
            addresses = [str(ipaddress.ip_address(host))]
        except ValueError:
            addresses = self.resolver(host)
        if not addresses:
            raise BlockedURL(f"Host '{host}' did not resolve.")
        for address in addresses:
            if not _is_public(address):
                raise BlockedURL(f"Host '{host}' resolves to a non-public address ({address}).")

    def fetch(self, url: str) -> FetchedDocument:
        current = url
        redirects: list[str] = []
        for _ in range(MAX_REDIRECTS + 1):
            self.validate_url(current)
            try:
                with self._client.stream("GET", current) as resp:
                    if resp.is_redirect:
                        location = resp.headers.get("location")
                        if not location:
                            raise FetchError("Redirect without Location header.")
                        redirects.append(current)
                        current = urljoin(current, location)
                        continue
                    if resp.status_code >= 400:
                        raise FetchError(f"HTTP {resp.status_code} for {current}")
                    body = bytearray()
                    for chunk in resp.iter_bytes():
                        body.extend(chunk)
                        if len(body) > self.settings.fetch_max_bytes:
                            raise FetchError(
                                f"Response exceeds {self.settings.fetch_max_bytes} bytes."
                            )
                    return FetchedDocument(
                        requested_url=url,
                        final_url=current,
                        status_code=resp.status_code,
                        content_type=resp.headers.get("content-type", "").split(";")[0].strip(),
                        body=bytes(body),
                        fetched_at=datetime.now(UTC),
                        redirects=redirects,
                    )
            except httpx.HTTPError as exc:
                raise FetchError(f"Fetching {current} failed: {exc}") from exc
        raise FetchError(f"Too many redirects (>{MAX_REDIRECTS}).")
