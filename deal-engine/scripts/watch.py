"""Easy mode: watch product URLs from config/watchlist.txt and post price drops to Slack.
No API keys, signups, Docker or Redis. Data is kept in a local SQLite file.

  python -m scripts.watch            # check every 30 minutes until you stop it (Ctrl+C)
  python -m scripts.watch --once     # check once and exit
  python -m scripts.watch --interval 15 --browser

Env: SLACK_WEBHOOK_URL, WATCH_MIN_DROP_PERCENT (default 5), WATCH_DATABASE_URL (default sqlite:///dealengine.db).
It obeys robots.txt and stops using a shop that refuses automated access (it never tries to get around that)."""
from __future__ import annotations

import hashlib
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

if __name__ == "__main__":  # decide the database BEFORE app modules read settings
    os.environ["DATABASE_URL"] = os.environ.get("WATCH_DATABASE_URL", "sqlite:///dealengine.db")

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.config.settings import Settings  # noqa: E402
from app.crawlers import registry  # noqa: E402
from app.crawlers.base import ProductCandidate, ProductNotFound, RetailerBlocked, RetailerError  # noqa: E402
from app.crawlers.public import PublicPageAdapter  # noqa: E402
from app.models.price import PriceObservation  # noqa: E402
from app.models.product import RetailerProduct  # noqa: E402
from app.models.retailer import Retailer  # noqa: E402
from app.notifiers.slack import SlackNotifier  # noqa: E402
from app.services import catalog, detection, notification_service, pipeline, retailer_health  # noqa: E402


def say(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def load_watchlist(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [ln.strip() for ln in path.read_text().splitlines() if ln.strip() and not ln.strip().startswith("#")]


def _host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def adapter_key_for(url: str) -> str:
    """Known retailer if the domain matches, otherwise create a generic adapter for that website."""
    host = _host(url)
    for key, cls in registry.ADAPTERS.items():
        if _host("https://" + cls.domain) == host:
            return key
    key = "site_" + re.sub(r"[^a-z0-9]+", "_", host).strip("_")
    if key not in registry.ADAPTERS:
        scheme = urlparse(url).scheme

        def pid(self, u: str) -> str:  # stable id from the page address
            return hashlib.sha1(urlparse(u).path.encode()).hexdigest()[:12]

        registry.ADAPTERS[key] = type(f"{key}Adapter", (PublicPageAdapter,), {
            "key": key, "name": host, "domain": urlparse(url).netloc, "scheme": scheme, "search_url": None,
            "sitemap_max_urls": 0, "product_id_from_url": pid,
            "access_policy": "Generic page watcher (robots.txt-gated)."})
    return key


def setup(session: Session, settings: Settings, urls: list[str]) -> int:
    registry.load_all(settings)
    keys = {u: adapter_key_for(u) for u in urls}
    catalog.sync_retailers(session, settings)
    added = 0
    for url, key in keys.items():
        retailer = retailer_health.get_retailer(session, key)
        retailer.active = True  # type: ignore[union-attr]
        ad = registry.get_adapter(key, settings)
        cand = ad.candidate_from_url(url) if isinstance(ad, PublicPageAdapter) else None
        if cand is None:
            say(f"  skipped (cannot read a product id from this address): {url}")
            continue
        _, created = catalog.upsert_listing(session, retailer, ProductCandidate(cand.retailer_product_id, url))  # type: ignore[arg-type]
        added += int(created)
    session.commit()
    return added


def _latest(session: Session, rp_id: int) -> PriceObservation | None:
    return session.scalar(select(PriceObservation).where(PriceObservation.retailer_product_id == rp_id)
                          .order_by(PriceObservation.timestamp.desc(), PriceObservation.id.desc()).limit(1))


def run_cycle(session: Session, settings: Settings, notifier: SlackNotifier, min_drop: float) -> dict[str, int]:
    out = {"checked": 0, "drops": 0, "deals": 0, "problems": 0}
    for rp in list(session.scalars(select(RetailerProduct).where(RetailerProduct.active.is_(True)))):
        retailer = session.get(Retailer, rp.retailer_id)
        prev = _latest(session, rp.id)
        try:
            scraped = pipeline.fetch(session, rp.id, settings)
        except RetailerBlocked as exc:
            say(f"  BLOCKED by {retailer.name}: {exc}. Not retrying; this shop is paused.")  # type: ignore[union-attr]
            out["problems"] += 1
            session.commit()
            continue
        except ProductNotFound:
            say(f"  page not found: {rp.product_url}")
            out["problems"] += 1
            continue
        except RetailerError as exc:
            say(f"  problem with {rp.product_url}: {exc}")
            out["problems"] += 1
            continue
        if scraped is None:
            continue
        pipeline.store(session, rp.id, scraped, settings)
        session.flush()
        new = _latest(session, rp.id)
        out["checked"] += 1
        say(f"  {scraped.title[:60]}: ₹{scraped.price:,.0f} at {retailer.name}")  # type: ignore[union-attr]
        if prev and new and new.id != prev.id and prev.availability and new.availability \
                and new.effective_price <= prev.effective_price * (1 - min_drop / 100):
            first = session.scalar(select(PriceObservation.timestamp).where(PriceObservation.retailer_product_id == rp.id)
                                   .order_by(PriceObservation.timestamp).limit(1))
            days = max(0, (new.timestamp - first).days) if first else 0
            try:
                notifier.send_quick_drop({
                    "title": scraped.title, "url": rp.product_url, "retailer_name": retailer.name,  # type: ignore[union-attr]
                    "old_price": prev.effective_price, "new_price": new.effective_price,
                    "rating": rp.rating, "review_count": rp.review_count, "history_days": days})
                say("  -> price drop sent to Slack")
                out["drops"] += 1
            except Exception as exc:  # noqa: BLE001
                say(f"  could not send to Slack: {exc}")
        if rp.product_id:
            ev = detection.detect_for_product(session, rp.product_id, settings)
            if ev is not None:
                session.flush()
                try:
                    notification_service.deliver(session, ev.id, settings)
                    out["deals"] += 1
                    say("  -> verified deal sent to Slack")
                except Exception as exc:  # noqa: BLE001
                    say(f"  could not send deal to Slack: {exc}")
        session.commit()
    return out


def main(argv: list[str]) -> int:
    from app.config.settings import get_settings
    from app.database.base import Base
    from app.database.session import get_engine, new_session
    from app.utils.logging import configure_logging

    configure_logging("WARNING")
    s = get_settings()
    if "--browser" in argv:
        for cls in registry.load_all(s).values():
            if issubclass(cls, PublicPageAdapter):
                cls.use_browser = True
        s.browser_enabled = True
    interval = float(argv[argv.index("--interval") + 1]) if "--interval" in argv else 30.0
    min_drop = float(os.environ.get("WATCH_MIN_DROP_PERCENT", "5"))
    notifier = SlackNotifier(s)
    if not notifier.is_configured():
        say("Slack is not set up: put SLACK_WEBHOOK_URL in your .env file. Continuing without alerts.")
    Base.metadata.create_all(get_engine())
    urls = load_watchlist(Path(s.config_dir) / "watchlist.txt")
    if not urls:
        say("Your watchlist is empty. Add product page URLs to config/watchlist.txt (one per line) and run again.")
        return 1
    with new_session() as session:
        added = setup(session, s, urls)
        say(f"Watching {len(urls)} product(s) ({added} new). Prices are checked every {interval:g} minutes.")
        while True:
            res = run_cycle(session, s, notifier, min_drop)
            say(f"Done: {res['checked']} checked, {res['drops']} price drops, {res['deals']} verified deals, "
                f"{res['problems']} problems.")
            if "--once" in argv:
                return 0
            time.sleep(interval * 60)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
