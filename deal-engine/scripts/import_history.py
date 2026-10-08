"""Import legally obtained historical prices (IMPORTED_HISTORY). CSV columns:
retailer,retailer_product_id,timestamp,price[,currency,in_stock]
Listings must already exist (run discovery first). Rows are stored as source=IMPORTED_HISTORY,
never as observed history. Usage: python -m scripts.import_history prices.csv"""
import csv
import sys
from datetime import datetime, timezone

from sqlalchemy import select

from app.crawlers.base import ScrapedProduct
from app.database.session import session_scope
from app.models.price import IMPORTED, PriceObservation
from app.models.product import RetailerProduct
from app.models.retailer import Retailer
from app.services import pricing


def main(path: str) -> None:
    n = skipped = 0
    with session_scope() as s, open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rp = s.scalar(select(RetailerProduct).join(Retailer, Retailer.id == RetailerProduct.retailer_id).where(
                Retailer.key == row["retailer"], RetailerProduct.retailer_product_id == row["retailer_product_id"]))
            if rp is None:
                skipped += 1
                continue
            ts = datetime.fromisoformat(row["timestamp"])
            ts = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
            exists = s.scalar(select(PriceObservation.id).where(
                PriceObservation.retailer_product_id == rp.id, PriceObservation.timestamp == ts,
                PriceObservation.source == IMPORTED))
            if exists:
                continue  # idempotent re-import
            p = ScrapedProduct(rp.retailer_product_id, rp.product_url, rp.title or "", float(row["price"]),
                               row.get("currency") or "INR",
                               (row.get("in_stock") or "true").lower() in ("1", "true", "yes"))
            if pricing.record_observation(s, rp, p, ts=ts, source=IMPORTED):
                n += 1
    print(f"imported={n} skipped_unknown_listing={skipped}")


if __name__ == "__main__":
    main(sys.argv[1])
