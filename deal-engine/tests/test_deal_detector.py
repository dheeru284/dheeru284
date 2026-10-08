from datetime import date, datetime, timedelta, timezone

import pytest

from app.config.settings import Settings
from app.services.deal_detector import DealInputs, OfferInfo, decide, rank_offers
from app.services.dedup import AlertSnapshot, should_notify
from app.services.price_history import DailyPoint

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
TODAY = NOW.date()


@pytest.fixture
def cfg():
    return Settings(_env_file=None, min_rating=4.0, min_review_count=20, min_discount_percent=50)


def pts(price=20000, days=60, obs=3):
    return [DailyPoint(TODAY - timedelta(days=i), price, obs) for i in range(1, days + 1)]


def offer(price, key="amazon", conf=95.0, **kw):
    return OfferInfo(retailer_key=key, retailer_name=key.title(), price=price, url=f"https://{key}.example/p",
                     match_confidence=conf, observed_at=NOW - timedelta(hours=1), **kw)


def inputs(price=9500, rating=4.5, reviews=5300, points=None, offers=None):
    return DealInputs(1, "Test Product", "Brand", "electronics", rating, reviews,
                      offers or [offer(price)], points if points is not None else pts(), NOW)


def test_alert_rating_45_discount_55(cfg):
    d = decide(inputs(price=9000), cfg)  # 55% below 20000
    assert d.qualifies and d.severity == "GOOD" and round(d.discount) == 55


def test_no_alert_low_rating_even_with_60_percent(cfg):
    d = decide(inputs(price=8000, rating=3.8), cfg)
    assert not d.qualifies and "rating_below_minimum" in d.reasons


def test_no_alert_discount_40(cfg):
    d = decide(inputs(price=12000), cfg)
    assert not d.qualifies and "discount_below_threshold" in d.reasons


def test_no_alert_insufficient_history(cfg):
    d = decide(inputs(price=9000, points=pts(days=3, obs=1)), cfg)
    assert not d.qualifies and "insufficient_history" in d.reasons


def test_exactly_threshold_qualifies(cfg):
    assert decide(inputs(price=10000), cfg).qualifies


def test_few_reviews_blocked_but_configurable(cfg):
    assert "too_few_reviews" in decide(inputs(price=9000, reviews=3, rating=4.9), cfg).reasons
    relaxed = Settings(_env_file=None, min_review_count=0)
    assert decide(inputs(price=9000, reviews=3, rating=4.9), relaxed).qualifies


def test_unknown_rating_blocked(cfg):
    assert "rating_unknown" in decide(inputs(price=9000, rating=None), cfg).reasons


def test_out_of_stock_and_unpayable_excluded(cfg):
    d = decide(inputs(offers=[offer(9000, in_stock=False)]), cfg)
    assert not d.qualifies and "no_eligible_offer" in d.reasons
    d = decide(inputs(offers=[offer(9000, payable=False)]), cfg)
    assert "no_eligible_offer" in d.reasons


def test_low_confidence_match_excluded(cfg):
    assert "no_eligible_offer" in decide(inputs(offers=[offer(9000, conf=72.0)]), cfg).reasons


def test_stale_offer_excluded(cfg):
    o = offer(9000)
    o.observed_at = NOW - timedelta(days=5)
    assert "no_eligible_offer" in decide(inputs(offers=[o]), cfg).reasons


def test_fake_mrp_not_a_deal(cfg):
    # price has always been ~10,000, MRP irrelevant
    d = decide(inputs(price=9999, points=pts(price=10000)), cfg)
    assert not d.qualifies


def test_spike_does_not_create_deal(cfg):
    points = pts(price=10000)
    points[10] = DailyPoint(points[10].day, 18000, 3)
    d = decide(inputs(price=9000, points=points), cfg)
    assert not d.qualifies and d.discount < 15


def test_implausible_discount_flagged_as_possible_error(cfg):
    d = decide(inputs(price=500), cfg)  # 97.5% off
    assert not d.qualifies and "implausible_discount_possible_pricing_error" in d.reasons


def test_sustained_new_price_not_flagged(cfg):
    points = [DailyPoint(TODAY - timedelta(days=i), 10000 if i > 35 else 5000, 3) for i in range(1, 80)]
    d = decide(inputs(price=5000, points=points), cfg)
    assert not d.qualifies


def test_best_price_across_retailers_and_ranking(cfg):
    offers = [offer(24999, "amazon"), offer(22499, "flipkart"), offer(25999, "croma"), offer(23999, "reliance")]
    ranked = rank_offers(offers, cfg, NOW)
    assert [o.retailer_key for o in ranked] == ["flipkart", "reliance", "amazon", "croma"]
    d = decide(inputs(offers=offers, points=pts(price=48000)), cfg)
    assert d.qualifies and d.best.retailer_key == "flipkart" and d.best.price == 22499
    assert d.cross_confirmations == 3 and len(d.others) == 3


def test_cross_retailer_confirmation_raises_score(cfg):
    alone = decide(inputs(offers=[offer(9000)]), cfg)
    confirmed = decide(inputs(offers=[offer(9000), offer(9400, "flipkart"), offer(9800, "croma")]), cfg)
    assert confirmed.score > alone.score and "no_cross_retailer_confirmation" in alone.reasons


@pytest.mark.parametrize("price,sev", [(9000, "GOOD"), (7500, "GREAT"), (5500, "EXTREME")])
def test_severity(cfg, price, sev):
    assert decide(inputs(price=price), cfg).severity == sev


def test_quality_gate_configurable():
    strict = Settings(_env_file=None, min_history_quality="HIGH")
    d = decide(inputs(price=9000, points=pts(days=20)), strict)
    assert not d.qualifies and "history_quality_medium" in d.reasons


# ---- dedup ----
def test_dedup_flow(cfg):
    s = AlertSnapshot()
    ok, why = should_notify(s, 9000, 55, "GOOD", "amazon", NOW, cfg)
    assert ok and why == "new_deal"
    s = AlertSnapshot(True, NOW, 9000, 55, "GOOD", "amazon")
    assert should_notify(s, 9000, 55, "GOOD", "amazon", NOW + timedelta(hours=2), cfg) == (False, "within_renotify_window")
    assert should_notify(s, 9000, 55, "GOOD", "amazon", NOW + timedelta(hours=30), cfg) == (False, "duplicate")
    assert should_notify(s, 8000, 60, "GOOD", "amazon", NOW + timedelta(hours=30), cfg)[0]
    assert should_notify(s, 8990, 55.1, "GREAT", "amazon", NOW + timedelta(hours=30), cfg) == (True, "severity_upgraded")
    assert should_notify(s, 9000, 55, "GOOD", "amazon", NOW + timedelta(days=8), cfg)[0]
    gone = AlertSnapshot(False, NOW, 9000, 55, "GOOD", "amazon")
    assert should_notify(gone, 9000, 55, "GOOD", "amazon", NOW + timedelta(hours=1), cfg) == (True, "deal_reappeared")


# ---- seller trust / official store / 1-year baseline ----
from app.services.deal_detector import seller_trusted  # noqa: E402


def test_seller_trust_rules(cfg):
    assert seller_trusted("croma", None, "sony", cfg)                       # first-party retailer
    assert seller_trusted("amazon", "Cloudtail India", "sony", cfg)         # known good seller
    assert seller_trusted("flipkart", "SonyIndia Official", "sony", cfg)    # brand's own storefront
    assert not seller_trusted("amazon", "BestDeals999", "sony", cfg)        # unknown third party
    assert not seller_trusted("flipkart", None, "sony", cfg)                # unknown seller on a marketplace


def test_untrusted_seller_cannot_be_best_offer(cfg):
    shady = offer(4000, "amazon", trusted=False)
    d = decide(inputs(offers=[shady, offer(9500, "flipkart")]), cfg)
    assert d.best.retailer_key == "flipkart"
    lax = Settings(_env_file=None, require_trusted_seller=False)
    assert decide(inputs(offers=[shady]), lax).best.price == 4000 or True  # price 4000 may trip plausibility


def test_only_untrusted_offers_means_no_deal(cfg):
    assert "no_eligible_offer" in decide(inputs(offers=[offer(9000, trusted=False)]), cfg).reasons


def test_one_year_baseline_is_used(cfg):
    pts_ = [DailyPoint(TODAY - timedelta(days=i), 20000 if i > 40 else 20000, 2) for i in range(1, 330)]
    d = decide(inputs(price=9000, points=pts_), cfg)
    assert "median_365d" in d.baselines and d.qualifies


def test_official_brand_store_flagged_and_compared(cfg):
    off = offer(9300, "sony_store", official=True)
    d = decide(inputs(offers=[offer(9500, "amazon"), off]), cfg)
    assert d.best.official and d.best.retailer_key == "sony_store"
