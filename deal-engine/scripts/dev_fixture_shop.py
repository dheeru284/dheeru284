"""Local stand-in for a retailer site + Slack webhook, for end-to-end smoke tests WITHOUT touching real sites.
Serves /robots.txt, /p/<id> pages with schema.org JSON-LD, POST /slack (records payloads, GET /slack/log shows them),
and POST /set?id=101&price=9500 to change prices. Usage: python -m scripts.dev_fixture_shop 8765"""
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PRODUCTS = {
    "101": {"name": "Sony WH-1000XM5 Wireless Noise Cancelling Headphones Black", "price": 20000, "rating": 4.5, "reviews": 5300},
    "9001": {"name": "Sony WH-1000XM5 Headphones (Black)", "price": 21000, "rating": 4.4, "reviews": 900},
}
SLACK: list[dict] = []


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
        u = urlparse(self.path)
        if u.path == "/robots.txt":
            return self._send(200, "User-agent: *\nAllow: /\n", "text/plain")
        if u.path == "/slack/log":
            return self._send(200, json.dumps(SLACK), "application/json")
        if u.path.startswith("/p/") and u.path[3:] in PRODUCTS:
            p = PRODUCTS[u.path[3:]]
            ld = {"@type": "Product", "name": p["name"], "sku": u.path[3:], "brand": {"name": "Sony"},
                  "aggregateRating": {"ratingValue": p["rating"], "reviewCount": p["reviews"]},
                  "offers": {"@type": "Offer", "price": p["price"], "priceCurrency": "INR",
                             "availability": "https://schema.org/InStock"}}
            return self._send(200, f"<script type='application/ld+json'>{json.dumps(ld)}</script>")
        self._send(404, "not found")

    def do_POST(self):
        u = urlparse(self.path)
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n) if n else b""
        if u.path == "/slack":
            SLACK.append(json.loads(body))
            return self._send(200, "ok", "text/plain")
        if u.path == "/set":
            q = parse_qs(u.query)
            PRODUCTS[q["id"][0]]["price"] = float(q["price"][0])
            return self._send(200, "set", "text/plain")
        self._send(404, "nf")


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1]) if len(sys.argv) > 1 else 8765), H).serve_forever()
