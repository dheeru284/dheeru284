"""Keepa API client: up to ~1 year+ of Amazon.in price history as IMPORTED_HISTORY.

Keepa (https://keepa.com/api-docs/) is a paid, official data API; set KEEPA_API_KEY. Domain 10 == Amazon India.
Format notes (from Keepa's public docs; NOT exercised against a live key here): `csv[1]` is the NEW-offer price
series as flat [keepaTime, price, keepaTime, price, ...]; keepaTime is minutes since 2011-01-01 UTC (add 21564000
to get Unix minutes); price is in 1/100 of the currency unit; -1 means unavailable."""
from __future__ import annotations

import os
from datetime import datetime, timezone

import httpx

KEEPA_DOMAIN_IN = 10
NEW_PRICE_INDEX = 1


def keepa_time_to_dt(kt: int) -> datetime:
    return datetime.fromtimestamp((kt + 21564000) * 60, tz=timezone.utc)


def parse_price_series(csv: list[int]) -> list[tuple[datetime, float | None]]:
    """-> [(timestamp, price_in_currency_units or None when unavailable)]"""
    out: list[tuple[datetime, float | None]] = []
    for i in range(0, len(csv) - 1, 2):
        price = csv[i + 1]
        out.append((keepa_time_to_dt(csv[i]), None if price < 0 else price / 100.0))
    return out


def fetch_history(asin: str, api_key: str | None = None, client: httpx.Client | None = None,
                  days: int = 365) -> list[tuple[datetime, float | None]]:
    key = api_key or os.environ.get("KEEPA_API_KEY")
    if not key:
        raise RuntimeError("KEEPA_API_KEY not set")
    c = client or httpx.Client(timeout=30)
    r = c.get("https://api.keepa.com/product", params={"key": key, "domain": KEEPA_DOMAIN_IN, "asin": asin,
                                                         "history": 1, "days": days})
    r.raise_for_status()
    prods = r.json().get("products") or []
    if not prods or not (prods[0].get("csv") or [None] * 2)[NEW_PRICE_INDEX]:
        return []
    return parse_price_series(prods[0]["csv"][NEW_PRICE_INDEX])
