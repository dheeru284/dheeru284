"""Currency conversion with a cached, configurable exchange-rate provider."""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import Settings, get_settings
from app.utils.logging import get_logger

log = get_logger(__name__)

SUPPORTED = ("INR", "USD", "AED", "SGD", "AUD", "EUR", "GBP", "CAD", "CHF", "JPY")
_mem: dict[str, tuple[float, float]] = {}  # currency -> (inr_per_unit, fetched_monotonic)


class FxUnavailable(RuntimeError):
    pass


def _fetch_provider(settings: Settings) -> dict[str, float]:
    """Returns INR-per-unit for supported currencies. Provider API shape: Frankfurter-compatible."""
    others = ",".join(c for c in SUPPORTED if c != "INR")
    resp = httpx.get(
        settings.fx_provider_url,
        params={"from": "INR", "to": others},
        timeout=settings.http_timeout_seconds,
    )
    resp.raise_for_status()
    rates = resp.json()["rates"]  # units of X per 1 INR
    return {cur: 1.0 / float(v) for cur, v in rates.items() if float(v) > 0}


def refresh_rates(session: Session, settings: Settings | None = None) -> dict[str, float]:
    from app.models.price import ExchangeRate

    settings = settings or get_settings()
    rates = _fetch_provider(settings)
    now = datetime.now(timezone.utc)
    for cur, inr in rates.items():
        row = session.get(ExchangeRate, cur)
        if row is None:
            session.add(ExchangeRate(currency=cur, inr_per_unit=inr, fetched_at=now, source="provider"))
        else:
            row.inr_per_unit, row.fetched_at, row.source = inr, now, "provider"
        _mem[cur] = (inr, time.monotonic())
    session.flush()
    return rates


def get_inr_rate(session: Session, currency: str, settings: Settings | None = None) -> float:
    """INR per 1 unit of `currency`. Cached in-process and in DB; the API is hit at most once per TTL."""
    from app.models.price import ExchangeRate

    settings = settings or get_settings()
    currency = currency.upper()
    if currency == "INR":
        return 1.0
    ttl = settings.fx_cache_ttl_hours * 3600
    hit = _mem.get(currency)
    if hit and time.monotonic() - hit[1] < ttl:
        return hit[0]
    row = session.scalar(select(ExchangeRate).where(ExchangeRate.currency == currency))
    if row is not None:
        fetched = row.fetched_at if row.fetched_at.tzinfo else row.fetched_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - fetched < timedelta(seconds=ttl):
            _mem[currency] = (row.inr_per_unit, time.monotonic())
            return row.inr_per_unit
    try:
        rates = refresh_rates(session, settings)
        if currency in rates:
            return rates[currency]
    except Exception as exc:  # network/provider failure -> degrade to stale or configured fallback
        log.warning("fx provider failed", extra={"error": str(exc)})
    if row is not None:
        return row.inr_per_unit  # stale but real
    fallback = settings.fallback_rates.get(currency)
    if fallback:
        return fallback
    raise FxUnavailable(f"no exchange rate available for {currency}")


def to_inr(session: Session, amount: float, currency: str, settings: Settings | None = None) -> float:
    return round(amount * get_inr_rate(session, currency, settings), 2)


def clear_cache() -> None:
    _mem.clear()


def format_inr(value: float | None) -> str:
    """Indian digit grouping: 129999 -> ₹1,29,999."""
    if value is None:
        return "n/a"
    whole = f"{round(value):d}"
    neg = whole.startswith("-")
    whole = whole.lstrip("-")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts: list[str] = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts) + "," + tail
    return f"{'-' if neg else ''}₹{whole}"
