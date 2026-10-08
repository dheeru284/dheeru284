import os

# Must be set before any app module reads settings.
os.environ["REDIS_URL"] = "redis://localhost:6399/0"  # unreachable -> in-memory fallbacks, no cross-test pollution
os.environ.setdefault("TEST_DATABASE_URL", "sqlite:////tmp/dealengine_test.db")
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
for k in list(os.environ):
    if k.startswith(("SLACK_", "FEED_")):
        del os.environ[k]

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: E402,F401
from app.database.base import Base  # noqa: E402


@pytest.fixture
def engine():
    eng = create_engine(os.environ["TEST_DATABASE_URL"])
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def session(engine):
    s = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)()
    yield s
    s.close()


class _Server:
    """Tiny HTTP server: serves product pages with JSON-LD, robots.txt, and captures Slack webhooks."""

    def __init__(self):
        self.prices: dict[str, dict] = {}
        self.slack: list[dict] = []
        self.slack_status = 200
        self.blocked_paths: set[str] = set()
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body, ctype="text/html"):
                data = body.encode()
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                if self.path == "/robots.txt":
                    return self._send(200, "User-agent: *\nDisallow: /private/\nAllow: /\n", "text/plain")
                if any(self.path.startswith(b) for b in outer.blocked_paths):
                    return self._send(403, "<html>Access Denied - captcha</html>")
                if self.path.startswith("/p/"):
                    info = outer.prices.get(self.path)
                    if not info:
                        return self._send(404, "nf")
                    ld = {"@context": "https://schema.org", "@type": "Product", "name": info["name"],
                          "sku": self.path.split("/")[-1], "brand": {"@type": "Brand", "name": info.get("brand", "Sony")},
                          "mpn": info.get("mpn"),
                          "aggregateRating": {"@type": "AggregateRating", "ratingValue": info.get("rating", 4.5),
                                              "reviewCount": info.get("reviews", 5300)},
                          "offers": {"@type": "Offer", "price": info["price"], "priceCurrency": "INR",
                                     "availability": "https://schema.org/" + ("InStock" if info.get("in_stock", True) else "OutOfStock")}}
                    return self._send(200, f"<html><head><script type='application/ld+json'>{json.dumps(ld)}</script></head></html>")
                if self.path.startswith("/private/"):
                    return self._send(200, "secret")
                self._send(404, "nf")

            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                outer.slack.append(json.loads(self.rfile.read(n)))
                self._send(outer.slack_status, "ok" if outer.slack_status == 200 else "err", "text/plain")

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    @property
    def domain(self):
        return f"127.0.0.1:{self.port}"

    def close(self):
        self.httpd.shutdown()


@pytest.fixture
def server():
    s = _Server()
    yield s
    s.close()
