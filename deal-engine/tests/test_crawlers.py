import json
from datetime import datetime, timezone

import httpx
import pytest

from app.config.settings import Settings
from app.crawlers.amazon import AmazonAdapter, sign_v4
from app.crawlers.base import ParseError, RetailerBlocked, RetailerNotConfigured
from app.crawlers.feed import FeedAdapter, parse_feed
from app.crawlers.http import Fetcher, looks_blocked
from app.crawlers.myntra import MyntraAdapter
from app.crawlers.parsers import parse_product_page, parse_sitemap
from app.crawlers.public import PublicPageAdapter
from app.crawlers.registry import ADAPTERS, get_adapter, load_all


def page(ld: dict | list) -> str:
    return f"<html><head><script type='application/ld+json'>{json.dumps(ld)}</script></head><body/></html>"


BASE = {"@type": "Product", "name": "Sony WH-1000XM5", "sku": "S1", "brand": {"name": "Sony"}, "mpn": "WH1000XM5/B",
        "gtin13": "4548736134935",
        "aggregateRating": {"ratingValue": "4.6", "reviewCount": "1,234"},
        "offers": {"@type": "Offer", "price": "24,990.00", "priceCurrency": "INR",
                   "availability": "https://schema.org/InStock", "seller": {"name": "RetailNet"}}}


def test_parse_jsonld_full():
    p = parse_product_page(page(BASE), "https://x.in/p/1")
    assert (p.title, p.price, p.currency, p.in_stock, p.rating, p.review_count) == (
        "Sony WH-1000XM5", 24990.0, "INR", True, 4.6, 1234)
    assert p.brand == "Sony" and p.gtin == "4548736134935" and p.seller == "RetailNet" and p.payable


def test_parse_graph_and_aggregate_offer_and_oos():
    ld = {"@graph": [{"@type": "WebPage"}, {**BASE, "offers": {"@type": "AggregateOffer", "offers": [
        {"price": 100, "priceCurrency": "INR", "availability": "https://schema.org/OutOfStock"}]}}]}
    p = parse_product_page(page(ld), "https://x.in/p/1")
    assert p.price == 100 and p.in_stock is False


def test_emi_and_refurbished_flagged_not_payable():
    emi = {**BASE, "offers": {**BASE["offers"], "name": "No cost EMI per month"}}
    assert parse_product_page(page(emi), "https://x.in/p/1").payable is False
    ref = {**BASE, "offers": {**BASE["offers"], "itemCondition": "https://schema.org/RefurbishedCondition"}}
    assert parse_product_page(page(ref), "https://x.in/p/1").condition == "refurbished"


def test_mrp_is_captured_informationally_only():
    ld = {**BASE, "offers": {**BASE["offers"], "priceSpecification": [{"priceType": "https://schema.org/ListPrice", "price": 40000}]}}
    p = parse_product_page(page(ld), "https://x.in/p/1")
    assert p.mrp == 40000 and p.price == 24990


def test_opengraph_fallback_and_parse_error():
    html = ("<meta property='og:title' content='Thing'/><meta property='product:price:amount' content='499'/>"
            "<meta property='product:price:currency' content='INR'/>")
    p = parse_product_page(html, "https://x.in/p/77", "77")
    assert p.price == 499 and p.title == "Thing"
    with pytest.raises(ParseError):
        parse_product_page("<html>nothing</html>", "https://x.in/p/1", "1")


def test_sitemap_parse():
    idx = "<sitemapindex><sitemap><loc>https://a/s1.xml</loc></sitemap></sitemapindex>"
    urls = "<urlset><url><loc>https://a/p/1</loc></url></urlset>"
    assert parse_sitemap(idx) == (["https://a/s1.xml"], [])
    assert parse_sitemap(urls) == ([], ["https://a/p/1"])


def test_block_detection():
    assert looks_blocked(403, "") and looks_blocked(429, "") and looks_blocked(200, "<html>Enter the characters you see below</html>")
    assert not looks_blocked(200, "<html>" + "x" * 30000)


def mk_fetcher(handler):
    s = Settings(_env_file=None, per_domain_min_interval_seconds=0, page_cache_ttl_seconds=0, redis_url="redis://localhost:6399/0")
    return Fetcher(s, httpx.Client(transport=httpx.MockTransport(handler), headers={"User-Agent": s.user_agent}))


def test_fetcher_respects_robots_disallow():
    def handler(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /search\n")
        return httpx.Response(200, text="ok")

    f = mk_fetcher(handler)
    assert f.get("https://shop.in/p/1").text == "ok"
    with pytest.raises(RetailerBlocked, match="robots"):
        f.get("https://shop.in/search?q=tv")


def test_fetcher_conservative_when_robots_unreachable_or_403():
    def deny(req):
        return httpx.Response(403) if req.url.path == "/robots.txt" else httpx.Response(200, text="ok")

    with pytest.raises(RetailerBlocked):
        mk_fetcher(deny).get("https://shop.in/p/1")

    def missing(req):
        return httpx.Response(404) if req.url.path == "/robots.txt" else httpx.Response(200, text="ok")

    assert mk_fetcher(missing).get("https://shop.in/p/1").text == "ok"  # no robots.txt == allowed


def test_fetcher_raises_blocked_on_403_and_captcha_no_evasion():
    calls = []

    def handler(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        calls.append(req.url)
        return httpx.Response(403, text="Access Denied")

    with pytest.raises(RetailerBlocked):
        mk_fetcher(handler).get("https://shop.in/p/1")
    assert len(calls) == 1  # no retry-with-different-headers loop


def test_search_not_permitted_by_robots_returns_empty():
    def handler(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /search\n")
        return httpx.Response(200, text="<a href='/p/1'>x</a>")

    class A(PublicPageAdapter):
        key, name, domain = "t", "T", "shop.in"
        search_url = "https://shop.in/search?q={query}"

    assert A(fetcher=mk_fetcher(handler)).search_products("tv") == []


def test_public_adapter_search_extracts_product_links():
    def handler(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, text="<a href='/foo/p/123?x=1'>a</a><a href='/foo/p/123'>dup</a><a href='/about'>b</a>")

    class A(PublicPageAdapter):
        key, name, domain = "t", "T", "shop.in"
        search_url = "https://shop.in/search?q={query}"
        product_url_re = r"/p/(?P<id>\d+)"

    out = A(fetcher=mk_fetcher(handler)).search_products("tv")
    assert [(c.retailer_product_id, c.url) for c in out] == [("123", "https://shop.in/foo/p/123")]


def test_registry_has_all_requested_retailers_and_feed_precedence(tmp_path, monkeypatch):
    load_all()
    for k in ["amazon", "flipkart", "myntra", "croma", "reliance_digital", "tata_cliq", "ajio", "nykaa",
              "meesho", "vijay_sales", "pepperfry", "ikea", "firstcry", "decathlon"]:
        assert k in ADAPTERS
    assert not get_adapter("croma").__class__.__name__.startswith("Feed")
    feed = tmp_path / "f.csv"
    feed.write_text("id,url,title,price,rating,review_count,in_stock\n1,https://c/p/1,Thing 4K,9999,4.4,200,true\n")
    monkeypatch.setenv("FEED_CROMA_URL", str(feed))
    ad = get_adapter("croma")
    assert isinstance(ad, FeedAdapter) and ad.is_configured()
    p = ad.fetch_listing("1", "https://c/p/1")
    assert p.price == 9999 and p.rating == 4.4 and p.review_count == 200
    assert ad.search_products("thing")[0].prefetched.price == 9999


def test_feed_parse_json_lines_and_mapping():
    txt = '{"sku": "a", "link": "https://x/a", "name": "A", "sale_price": "₹1,299", "stock": "no"}'
    items = parse_feed(txt, {"id": "sku", "url": "link", "title": "name", "price": "sale_price", "in_stock": "stock"})
    assert items[0].price == 1299 and items[0].in_stock is False


def test_amazon_requires_credentials_and_signs_requests():
    ad = AmazonAdapter(Settings(_env_file=None))
    assert not ad.is_configured()
    with pytest.raises(RetailerNotConfigured):
        ad.search_products("tv")
    h = sign_v4("AKID", "SECRET", "eu-west-1", "webservices.amazon.in", "/paapi5/searchitems",
                "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems", "{}",
                datetime(2026, 10, 8, tzinfo=timezone.utc))
    assert h["Authorization"].startswith("AWS4-HMAC-SHA256 Credential=AKID/20261008/eu-west-1/ProductAdvertisingAPI/aws4_request")
    assert "SECRET" not in json.dumps(h)


def test_amazon_item_mapping_and_api_errors():
    item = {"ASIN": "B0TEST", "DetailPageURL": "https://www.amazon.in/dp/B0TEST",
            "ItemInfo": {"Title": {"DisplayValue": "Sony WH-1000XM5"}, "ByLineInfo": {"Brand": {"DisplayValue": "Sony"}},
                         "ExternalIds": {"EANs": {"DisplayValues": ["4548736134935"]}}},
            "Offers": {"Listings": [{"Price": {"Amount": 24990.0, "Currency": "INR"}, "Availability": {"Type": "Now"},
                                     "Condition": {"Value": "New"}, "MerchantInfo": {"Name": "Appario"},
                                     "SavingBasis": {"Amount": 34990.0}}]}}
    p = AmazonAdapter._item_to_product(item)
    assert p.price == 24990 and p.in_stock and p.gtin == "4548736134935" and p.rating is None and p.mrp == 34990

    s = Settings(_env_file=None, amazon_paapi_access_key="a", amazon_paapi_secret_key="b", amazon_paapi_partner_tag="t-21")
    ad = AmazonAdapter(s, httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(429))))
    with pytest.raises(RetailerBlocked):
        ad.fetch_product("https://www.amazon.in/dp/B0TEST")
    ok = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"ItemsResult": {"Items": [item]}})))
    assert AmazonAdapter(s, ok).fetch_product("https://www.amazon.in/dp/B0TEST").retailer_product_id == "B0TEST"
