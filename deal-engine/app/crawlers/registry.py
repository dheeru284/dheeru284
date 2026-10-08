"""Adapter registry. To add a retailer: subclass RetailerAdapter (or PublicPageAdapter), decorate
with @register, and import the module in `load_all()` - or declare it in config/retailers.yaml."""
from __future__ import annotations

import importlib
import os
from pathlib import Path

import yaml

from app.config.settings import Settings, get_settings
from app.crawlers.base import RetailerAdapter

ADAPTERS: dict[str, type[RetailerAdapter]] = {}
_MODULES = (
    "amazon", "flipkart", "myntra", "croma", "reliance", "tatacliq", "ajio", "nykaa", "others",
)


def register(cls: type[RetailerAdapter]) -> type[RetailerAdapter]:
    ADAPTERS[cls.key] = cls
    return cls


def load_all(settings: Settings | None = None) -> dict[str, type[RetailerAdapter]]:
    for m in _MODULES:
        importlib.import_module(f"app.crawlers.{m}")
    _load_yaml_retailers(settings or get_settings())
    return ADAPTERS


def _load_yaml_retailers(settings: Settings) -> None:
    """Retailers declared in config/retailers.yaml become PublicPageAdapter subclasses (no code)."""
    from app.crawlers.public import PublicPageAdapter

    path = Path(settings.config_dir) / "retailers.yaml"
    if not path.exists():
        return
    data = yaml.safe_load(path.read_text()) or {}
    for key, spec in (data.get("retailers") or {}).items():
        if key in ADAPTERS:
            continue
        attrs = {
            "key": key, "name": spec.get("name", key.title()), "domain": spec["domain"],
            "search_url": spec.get("search_url"), "product_url_re": spec.get("product_url_re", r"/p/(?P<id>[\w-]+)"),
            "country": spec.get("country", "IN"), "currency": spec.get("currency", "INR"),
            "scheme": spec.get("scheme", "https"), "sitemap_max_urls": spec.get("sitemap_max_urls", 200),
            "access_policy": spec.get("access_policy", "Public pages, robots.txt-gated."),
        }
        ADAPTERS[key] = type(f"{key.title()}Adapter", (PublicPageAdapter,), attrs)


def is_enabled(key: str, settings: Settings) -> bool:
    if hasattr(settings, f"enable_{key}"):
        return settings.retailer_enabled(key)
    return os.environ.get(f"ENABLE_{key.upper()}", "true").lower() in ("1", "true", "yes")


def get_adapter(key: str, settings: Settings | None = None) -> RetailerAdapter:
    """Return the adapter for `key`; a configured FEED_<KEY>_URL takes precedence over page/API access."""
    from app.crawlers.feed import FeedAdapter

    settings = settings or get_settings()
    load_all(settings)
    cls = ADAPTERS[key]
    if os.environ.get(f"FEED_{key.upper()}_URL"):
        return FeedAdapter(cls, settings)  # type: ignore[arg-type]
    return cls(settings)  # type: ignore[call-arg]
