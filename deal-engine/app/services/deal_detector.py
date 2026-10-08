"""Deal decision logic. `decide()` is pure (no I/O) so every rule is unit-testable."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from app.config.settings import HISTORY_QUALITY_ORDER, Settings
from app.services.price_history import (
    DailyPoint,
    HistoryStats,
    baseline_candidates,
    compute_stats,
    discount_pct,
    select_baseline,
    trend_pct,
)


@dataclass
class OfferInfo:
    retailer_key: str
    retailer_name: str
    price: float  # effective INR price
    url: str
    in_stock: bool = True
    payable: bool = True
    match_confidence: float = 100.0
    observed_at: datetime | None = None
    seller: str | None = None
    listing_id: int | None = None
    trusted: bool = True
    official: bool = False  # the brand's own store


@dataclass
class DealInputs:
    product_id: int
    name: str
    brand: str | None
    category: str | None
    rating: float | None
    review_count: int | None
    offers: list[OfferInfo]
    points: list[DailyPoint]  # market daily-min series (all days incl. today)
    now: datetime
    uses_imported: bool = False  # True only if IMPORTED_HISTORY rows actually feed the series


@dataclass
class DealDecision:
    qualifies: bool
    reasons: list[str] = field(default_factory=list)  # why rejected (or flags when qualifying)
    best: OfferInfo | None = None
    others: list[OfferInfo] = field(default_factory=list)
    baseline_price: float | None = None
    baseline_type: str | None = None
    discount: float | None = None
    discount_from_max: float | None = None
    discount_from_median: float | None = None
    discount_from_average: float | None = None
    score: float = 0.0
    confidence: str = "LOW"
    severity: str | None = None
    history_quality: str = "LOW"
    stats: HistoryStats | None = None
    baselines: dict[str, float] = field(default_factory=dict)
    trend_30d: float | None = None
    trend_90d: float | None = None
    range_90d: tuple[float, float] | None = None
    cross_confirmations: int = 0
    market_discount_pct: float | None = None

    @property
    def near_miss(self) -> bool:
        """Close to qualifying - worth crawling more frequently."""
        return self.discount is not None and self.discount >= 30.0


def rank_offers(offers: list[OfferInfo], settings: Settings, now: datetime) -> list[OfferInfo]:
    """Eligible offers only (in stock, payable, fresh, confidently matched), cheapest first."""
    cutoff = now - timedelta(hours=settings.price_freshness_hours)
    ok = []
    for o in offers:
        if not (o.in_stock and o.payable and o.price > 0):
            continue
        if o.match_confidence < settings.min_match_confidence_for_deals:
            continue
        if settings.require_trusted_seller and not o.trusted:
            continue
        if o.observed_at is not None:
            seen = o.observed_at if o.observed_at.tzinfo else o.observed_at.replace(tzinfo=timezone.utc)
            if seen < cutoff:
                continue
        ok.append(o)
    return sorted(ok, key=lambda o: (o.price, o.retailer_key))


def seller_trusted(retailer_key: str, seller: str | None, brand: str | None, settings: Settings) -> bool:
    """First-party retailers and brand-official stores are trusted; on marketplaces the seller must be known and
    on the trusted list (or be the brand itself). Unknown seller on a marketplace == untrusted."""
    if retailer_key in settings.first_party_list or retailer_key in settings.official_list:
        return True
    if not seller:
        return False
    low = seller.lower()
    if brand and brand.lower() in low:
        return True  # brand's official storefront on a marketplace
    return any(t in low for t in settings.trusted_seller_list)


def severity_for(discount: float) -> str | None:
    if discount >= 70:
        return "EXTREME"
    if discount >= 60:
        return "GREAT"
    if discount >= 50:
        return "GOOD"
    return None


def _score(d: DealDecision, rating: float, reviews: int, best: OfferInfo, stats: HistoryStats) -> float:
    discount_pts = min(d.discount or 0.0, 80.0) / 80.0 * 30.0
    quality_pts = {"LOW": 5.0, "MEDIUM": 15.0, "HIGH": 25.0}[stats.quality]
    review_pts = min(1.0, reviews / 500.0) * 7.0 + max(0.0, min(1.0, (rating - 3.5) / 1.5)) * 8.0
    cross_pts = min(d.cross_confirmations, 2) / 2.0 * 15.0
    vol = stats.volatility if stats.volatility is not None else 0.5
    stability_pts = max(0.0, 1.0 - min(vol, 0.5) / 0.5) * 10.0
    match_pts = (best.match_confidence - 80.0) / 20.0 * 10.0
    return round(max(0.0, min(100.0, discount_pts + quality_pts + review_pts + cross_pts + stability_pts + match_pts)), 1)


def decide(inp: DealInputs, settings: Settings) -> DealDecision:
    d = DealDecision(qualifies=False)
    today = inp.now.date() if isinstance(inp.now, datetime) else inp.now
    eligible = rank_offers(inp.offers, settings, inp.now)
    if not eligible:
        d.reasons.append("no_eligible_offer")  # out of stock / stale / low-confidence match / not payable
        return d
    best = eligible[0]
    d.best, d.others = best, eligible[1:]

    stats = compute_stats(inp.points, today, settings.min_observations)
    d.stats, d.history_quality = stats, stats.quality

    # --- trends / ranges (informational) ---
    d.trend_30d = trend_pct(best.price, stats.avg.get(30))
    d.trend_90d = trend_pct(best.price, stats.avg.get(90))
    d.range_90d = stats.window_range(90, inp.points, today)

    # --- baseline from observed history only (MRP is never consulted) ---
    d.baselines = baseline_candidates(inp.points, today)
    chosen = select_baseline(d.baselines)
    if chosen:
        d.baseline_type, d.baseline_price = chosen
        d.discount = discount_pct(d.baseline_price, best.price)
        d.market_discount_pct = d.discount
    d.discount_from_max = discount_pct(stats.robust_max, best.price)
    d.discount_from_median = discount_pct(stats.median, best.price)
    d.discount_from_average = discount_pct(stats.average, best.price)
    d.cross_confirmations = sum(1 for o in d.others if o.price <= best.price * 1.25)

    # --- gates ---
    if stats.insufficient:
        d.reasons.append("insufficient_history")
    if HISTORY_QUALITY_ORDER[stats.quality] < HISTORY_QUALITY_ORDER[settings.min_history_quality.upper()]:
        d.reasons.append(f"history_quality_{stats.quality.lower()}")
    if chosen is None and "insufficient_history" not in d.reasons:
        d.reasons.append("no_credible_baseline")
    if inp.rating is None:
        d.reasons.append("rating_unknown")
    elif inp.rating < settings.min_rating:
        d.reasons.append("rating_below_minimum")
    if settings.min_review_count > 0 and (inp.review_count or 0) < settings.min_review_count:
        d.reasons.append("too_few_reviews")
    if d.discount is not None:
        if d.discount < settings.min_discount_percent:
            d.reasons.append("discount_below_threshold")
        elif d.discount > settings.max_plausible_discount:
            d.reasons.append("implausible_discount_possible_pricing_error")
        elif d.discount_from_max is not None and d.discount_from_max < settings.min_discount_percent:
            d.reasons.append("not_below_robust_historical_max")

    if d.reasons:
        return d

    d.qualifies = True
    d.severity = severity_for(d.discount or 0.0)
    d.score = _score(d, inp.rating or 0.0, inp.review_count or 0, best, stats)
    d.confidence = "HIGH" if d.score >= 80 else "MEDIUM" if d.score >= 60 else "LOW"
    if d.cross_confirmations == 0:
        d.reasons.append("no_cross_retailer_confirmation")
    if stats.quality != "HIGH":
        d.reasons.append(f"history_quality_{stats.quality.lower()}")
    return d


# ----------------------------------------------------------------- DB assembly ---

def build_inputs(session, product_id: int, settings: Settings, now: datetime | None = None) -> DealInputs | None:  # type: ignore[no-untyped-def]
    from sqlalchemy import func, select

    from app.models.price import IMPORTED, OBSERVED, DailyPrice, PriceObservation
    from app.models.product import Product, RetailerProduct
    from app.models.retailer import Retailer

    now = now or datetime.now(timezone.utc)
    product = session.get(Product, product_id)
    if product is None:
        return None
    rows = session.execute(
        select(RetailerProduct, Retailer).join(Retailer, Retailer.id == RetailerProduct.retailer_id)
        .where(RetailerProduct.product_id == product_id, RetailerProduct.active.is_(True), Retailer.active.is_(True))
    ).all()
    offers: list[OfferInfo] = []
    rated_num = rated_den = reviews = 0.0
    for rp, ret in rows:
        latest = session.scalar(
            select(PriceObservation).where(PriceObservation.retailer_product_id == rp.id)
            .order_by(PriceObservation.timestamp.desc()).limit(1)
        )
        if latest is not None:
            offers.append(OfferInfo(
                retailer_key=ret.key, retailer_name=ret.name, price=latest.effective_price, url=rp.product_url,
                in_stock=bool(latest.availability), payable=bool(latest.is_payable),
                match_confidence=rp.match_confidence or 0.0, observed_at=latest.timestamp,
                seller=latest.seller or rp.seller, listing_id=rp.id,
                trusted=seller_trusted(ret.key, latest.seller or rp.seller, product.brand, settings),
                official=ret.key in settings.official_list,
            ))
        if rp.rating is not None and rp.review_count and (rp.match_confidence or 0) >= settings.min_match_confidence_for_deals:
            rated_num += rp.rating * rp.review_count
            rated_den += rp.review_count
            reviews += rp.review_count
    rating = round(rated_num / rated_den, 2) if rated_den else None

    sources = [OBSERVED] + ([IMPORTED] if settings.allow_imported_history else [])  # ESTIMATED never counts
    listing_ids = [rp.id for rp, _ in rows if (rp.match_confidence or 0) >= settings.min_match_confidence_for_deals]
    points: list[DailyPoint] = []
    uses_imported = False
    if listing_ids:
        q = (
            select(DailyPrice.day, func.min(DailyPrice.min_price), func.sum(DailyPrice.obs_count))
            .where(DailyPrice.retailer_product_id.in_(listing_ids), DailyPrice.source.in_(sources))
            .group_by(DailyPrice.day).order_by(DailyPrice.day)
        )
        points = [DailyPoint(day=r[0], price=float(r[1]), obs_count=int(r[2])) for r in session.execute(q)]
        if settings.allow_imported_history:
            uses_imported = session.scalar(select(func.count()).select_from(DailyPrice).where(
                DailyPrice.retailer_product_id.in_(listing_ids), DailyPrice.source == IMPORTED)) > 0
    return DealInputs(
        product_id=product.id, name=product.canonical_name, brand=product.brand, category=product.category,
        rating=rating, review_count=int(reviews) if reviews else None, offers=offers, points=points, now=now,
        uses_imported=uses_imported,
    )


def today_utc(now: datetime) -> date:
    return now.astimezone(timezone.utc).date()
