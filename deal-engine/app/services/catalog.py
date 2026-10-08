"""Catalog: retailers, listings and canonical-product assignment."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config.settings import Settings, get_settings
from app.crawlers import registry
from app.crawlers.base import ProductCandidate, ScrapedProduct
from app.models.product import Product, RetailerProduct
from app.models.retailer import Retailer
from app.services import metrics
from app.services.product_matching import AUTO_MERGE_THRESHOLD, Features, find_best_match
from app.utils.normalization import normalize_gtin, normalize_mpn

MAX_CANDIDATES = 400


def sync_retailers(session: Session, settings: Settings | None = None) -> list[Retailer]:
    """Create/refresh Retailer rows from the adapter registry + ENABLE_* flags + credentials."""
    s = settings or get_settings()
    registry.load_all(s)
    out = []
    for key, cls in registry.ADAPTERS.items():
        row = session.scalar(select(Retailer).where(Retailer.key == key))
        if row is None:
            row = Retailer(key=key, name=cls.name, domain=cls.domain, country=cls.country, currency=cls.currency)
            session.add(row)
        row.active = registry.is_enabled(key, s)
        adapter = registry.get_adapter(key, s)
        if not adapter.is_configured():
            row.status, row.status_reason = "unconfigured", f"Missing credentials/feed. {cls.access_policy}"
        elif row.status == "unconfigured":
            row.status, row.status_reason = "ok", None
        out.append(row)
    session.flush()
    return out


def _title_hash(title: str, variant: str | None) -> str:
    return hashlib.sha1(f"{title}|{variant or ''}".encode()).hexdigest()[:12]


def upsert_listing(session: Session, retailer: Retailer, cand: ProductCandidate | ScrapedProduct,
                   category: str | None = None) -> tuple[RetailerProduct, bool]:
    pid = cand.retailer_product_id
    rp = session.scalar(select(RetailerProduct).where(
        RetailerProduct.retailer_id == retailer.id, RetailerProduct.retailer_product_id == str(pid)))
    created = rp is None
    if rp is None:
        rp = RetailerProduct(retailer_id=retailer.id, retailer_product_id=str(pid), product_url=cand.url)
        session.add(rp)
    rp.product_url = cand.url
    if getattr(cand, "title", None):
        rp.title = cand.title
    rp.category = category or getattr(cand, "category", None) or rp.category
    session.flush()
    return rp, created


def apply_scrape(rp: RetailerProduct, p: ScrapedProduct) -> None:
    rp.title, rp.product_url = p.title, p.url
    rp.brand = p.brand or rp.brand
    rp.category = p.category or rp.category
    rp.gtin = normalize_gtin(p.gtin) or rp.gtin
    rp.mpn = normalize_mpn(p.mpn) or rp.mpn
    rp.image_url = p.image_url or rp.image_url
    if p.rating is not None:
        rp.rating = p.rating
    if p.review_count is not None:
        rp.review_count = p.review_count
    rp.availability = p.in_stock
    rp.seller = p.seller or rp.seller
    rp.variant = p.variant or rp.variant
    attrs_condition = p.condition
    rp.match_notes = {**(rp.match_notes or {}), "condition": attrs_condition, "model_hint": p.model}


def assign_product(session: Session, rp: RetailerProduct, settings: Settings | None = None) -> Product | None:
    """Link the listing to a canonical Product (or create one). Idempotent: re-runs only when the
    listing's title/variant changed or it is still unassigned."""
    if not rp.title:
        return None
    th = _title_hash(rp.title, rp.variant)
    notes = dict(rp.match_notes or {})
    if rp.product_id is not None and notes.get("title_hash") == th:
        return rp.product

    cond = notes.get("condition")
    title_for_features = f"{rp.title} {cond}" if cond and cond not in rp.title.lower() else rp.title
    feat = Features.build(title_for_features, brand=rp.brand, gtin=rp.gtin, mpn=rp.mpn,
                          variant=rp.variant, model=notes.get("model_hint"))
    conds = []
    if feat.gtin:
        conds.append(Product.gtin == feat.gtin)
    if feat.mpn:
        conds.append(Product.manufacturer_part_number == feat.mpn)
    if feat.brand:
        conds.append(Product.brand == feat.brand)
    candidates: list[Product] = []
    if conds:
        candidates = list(session.scalars(select(Product).where(or_(*conds)).limit(MAX_CANDIDATES)))
    match, result, runners = find_best_match(candidates, feat, AUTO_MERGE_THRESHOLD)

    if match is not None:
        product, confidence = match, result.score
        if feat.gtin and not product.gtin:
            product.gtin = feat.gtin
        if feat.mpn and not product.manufacturer_part_number:
            product.manufacturer_part_number = feat.mpn
        metrics.inc("listings_matched")
    else:
        model = sorted(feat.attrs.model_tokens, key=len, reverse=True)
        product = Product(
            canonical_name=rp.title, brand=feat.brand, model=model[0] if model else None,
            category=rp.category, gtin=feat.gtin, manufacturer_part_number=feat.mpn,
            normalized_attributes=feat.attrs.to_dict(), core_tokens=sorted(feat.core),
        )
        session.add(product)
        session.flush()
        confidence = 100.0  # canonical product was created from this very listing
        metrics.inc("products_created")
    rp.product_id = product.id
    rp.match_confidence = round(confidence, 1)
    rp.match_notes = {**notes, "title_hash": th, "reasons": result.reasons if match else ["new_canonical_product"],
                      "possible_matches": runners}
    rp.attributes = feat.attrs.to_dict()
    session.flush()
    return product


def now() -> datetime:
    return datetime.now(timezone.utc)
