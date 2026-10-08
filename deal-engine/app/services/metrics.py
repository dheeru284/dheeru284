"""Cross-process counters (Redis hash, in-memory fallback), exposed at /metrics."""
from __future__ import annotations

import threading
from collections import defaultdict

from app.config.settings import get_settings

COUNTERS = (
    "products_scanned", "crawls_succeeded", "crawls_failed", "prices_recorded", "prices_skipped_unchanged",
    "deals_detected", "slack_alerts_sent", "slack_alerts_failed", "duplicate_alerts_suppressed",
    "retailer_blocked", "products_created", "listings_matched",
)
_mem: dict[str, float] = defaultdict(float)
_lock = threading.Lock()
_redis = None
_tried = False
KEY = "dealengine:metrics"


def _client():  # type: ignore[no-untyped-def]
    global _redis, _tried
    if not _tried:
        _tried = True
        try:
            import redis

            r = redis.Redis.from_url(get_settings().redis_url, socket_connect_timeout=1, socket_timeout=1)
            r.ping()
            _redis = r
        except Exception:
            _redis = None
    return _redis


def inc(name: str, n: float = 1, retailer: str | None = None) -> None:
    keys = [name] + ([f"{name}{{retailer={retailer}}}"] if retailer else [])
    r = _client()
    for k in keys:
        if r is not None:
            try:
                r.hincrbyfloat(KEY, k, n)
                continue
            except Exception:
                pass
        with _lock:
            _mem[k] += n


def snapshot() -> dict[str, float]:
    out: dict[str, float] = {c: 0.0 for c in COUNTERS}
    r = _client()
    if r is not None:
        try:
            out.update({k.decode(): float(v) for k, v in r.hgetall(KEY).items()})
            return out
        except Exception:
            pass
    with _lock:
        out.update(_mem)
    return out


def render_prometheus() -> str:
    lines = []
    for k, v in sorted(snapshot().items()):
        if "{" in k:
            name, rest = k.split("{", 1)
            label = rest.rstrip("}").split("=", 1)
            lines.append(f'dealengine_{name}_total{{{label[0]}="{label[1]}"}} {v}')
        else:
            lines.append(f"# TYPE dealengine_{k}_total counter")
            lines.append(f"dealengine_{k}_total {v}")
    return "\n".join(lines) + "\n"


def reset_for_tests() -> None:
    global _redis, _tried
    with _lock:
        _mem.clear()
    _redis, _tried = None, True
