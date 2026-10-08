"""Backfill ~1 year of Amazon.in price history from Keepa for every known Amazon listing (IMPORTED_HISTORY).
Needs KEEPA_API_KEY. Idempotent. Usage: python -m scripts.import_keepa [--days 365]"""
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.crawlers import keepa
from app.crawlers.base import ScrapedProduct
from app.database.session import session_scope
from app.models.price import IMPORTED, PriceObservation
from app.models.product import RetailerProduct
from app.models.retailer import Retailer
from app.services import pricing


def main(days: int = 365) -> None:
    n = 0
    with session_scope() as s:
        rps = s.scalars(select(RetailerProduct).join(Retailer, Retailer.id == RetailerProduct.retailer_id)
                        .where(Retailer.key == "amazon"))
        for rp in rps:
            last_day = None
            for ts, price in keepa.fetch_history(rp.retailer_product_id, days=days):
                if price is None or ts < datetime.now(timezone.utc) - timedelta(days=days):
                    continue
                if last_day == ts.date() and price is not None:
                    continue  # one point per day is enough for the daily roll-up
                last_day = ts.date()
                if s.scalar(select(PriceObservation.id).where(
                        PriceObservation.retailer_product_id == rp.id, PriceObservation.timestamp == ts,
                        PriceObservation.source == IMPORTED)):
                    continue
                p = ScrapedProduct(rp.retailer_product_id, rp.product_url, rp.title or "", price, "INR", True)
                if pricing.record_observation(s, rp, p, ts=ts, source=IMPORTED):
                    n += 1
    print(f"imported {n} Keepa price points")


if __name__ == "__main__":
    main(int(sys.argv[sys.argv.index("--days") + 1]) if "--days" in sys.argv else 365)
