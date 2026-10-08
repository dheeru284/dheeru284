from datetime import datetime, timezone

import httpx

from app.crawlers import keepa


def test_keepa_time_and_price_parsing():
    unix_min = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp() // 60)
    kt = unix_min - 21564000
    series = keepa.parse_price_series([kt, 2499900, kt + 1440, -1])
    assert series[0] == (datetime(2026, 1, 1, tzinfo=timezone.utc), 24999.0) and series[1][1] is None


def test_keepa_fetch_uses_india_domain():
    seen = {}

    def handler(req):
        seen.update(dict(req.url.params))
        return httpx.Response(200, json={"products": [{"csv": [None, [100, 500000]]}]})

    out = keepa.fetch_history("B0TEST", "k", httpx.Client(transport=httpx.MockTransport(handler)))
    assert seen["domain"] == "10" and out[0][1] == 5000.0
