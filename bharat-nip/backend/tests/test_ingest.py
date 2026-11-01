from datetime import UTC, datetime

import httpx
import pytest

from app.core.config import Settings
from app.ingest.extract import extract_document, extract_html, extract_pdf, sniff_content_type
from app.ingest.fetcher import BlockedURL, FetchError, SafeFetcher
from tests.helpers import PNG_1X1, make_text_pdf

PUBLIC_IP = "93.184.216.34"


def fetcher(handler, resolve=lambda host: [PUBLIC_IP], **kw):
    settings = Settings(_env_file=None, env="test", **kw)
    return SafeFetcher(settings, transport=httpx.MockTransport(handler), resolver=resolve)


@pytest.mark.parametrize(
    "url",
    [
        "http://example.org/",  # plain http refused by default
        "ftp://example.org/x",
        "https://user:pw@example.org/",
        "https://127.0.0.1/admin",
        "https://10.0.0.5/",
        "https://169.254.169.254/latest/meta-data/",  # cloud metadata
        "https://[::1]/",
    ],
)
def test_blocked_urls(url):
    f = fetcher(lambda r: httpx.Response(200, text="x"))
    with pytest.raises(BlockedURL):
        f.fetch(url)


def test_hostname_resolving_to_private_address_is_blocked():
    f = fetcher(lambda r: httpx.Response(200, text="x"), resolve=lambda h: ["192.168.1.10"])
    with pytest.raises(BlockedURL, match="non-public"):
        f.fetch("https://intranet.example.org/")


def test_redirect_to_private_address_is_blocked():
    def handler(request):
        return httpx.Response(302, headers={"location": "https://127.0.0.1/secret"})

    with pytest.raises(BlockedURL):
        fetcher(handler).fetch("https://example.org/start")


def test_size_limit_enforced():
    f = fetcher(lambda r: httpx.Response(200, content=b"x" * 2000), fetch_max_bytes=1000)
    with pytest.raises(FetchError, match="exceeds"):
        f.fetch("https://example.org/big")


def test_successful_fetch_follows_safe_redirect():
    def handler(request):
        if request.url.path == "/a":
            return httpx.Response(301, headers={"location": "/b"})
        return httpx.Response(200, text="<p>hi</p>", headers={"content-type": "text/html"})

    doc = fetcher(handler).fetch("https://example.org/a")
    assert doc.final_url == "https://example.org/b"
    assert doc.redirects == ["https://example.org/a"]
    assert doc.content_type == "text/html"


HTML = """<html lang="en"><head><title>Fallback</title>
<meta property="og:title" content="Budget speech fact sheet">
<meta property="og:site_name" content="Example Gazette">
<meta property="article:published_time" content="2024-02-01T09:00:00Z">
<script>var tracking = 1;</script></head>
<body><nav>Home | About</nav><article><h1>Budget speech fact sheet</h1>
<p>The deficit target is 4.5 percent of output.</p><p>Spending rises 6 percent.</p></article>
<footer>Copyright</footer></body></html>"""


def test_html_extraction():
    doc = extract_html(HTML)
    assert doc.title == "Budget speech fact sheet"
    assert doc.publisher == "Example Gazette"
    assert doc.published_at == datetime(2024, 2, 1, 9, tzinfo=UTC)
    assert "deficit target is 4.5 percent" in doc.text
    assert "tracking" not in doc.text and "Home | About" not in doc.text
    assert doc.language == "en"


def test_pdf_extraction_and_sniffing():
    pdf = make_text_pdf(["Riverland budget statement 2024.", "Deficit target 4.5 percent."])
    assert sniff_content_type(pdf) == "application/pdf"
    doc = extract_pdf(pdf)
    assert doc is not None and "Deficit target 4.5 percent" in doc.text
    assert extract_document("application/pdf", pdf).text == doc.text
    assert sniff_content_type(PNG_1X1) == "image/png"
    assert sniff_content_type(b"<html>") is None


def test_pdf_without_text_layer_returns_none():
    assert extract_pdf(make_text_pdf([])) is None
