"""Extract product data from schema.org JSON-LD / OpenGraph (the machine-readable data sites
publish for search engines). No site-specific CSS scraping."""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.crawlers.base import ParseError, ScrapedProduct
from app.utils.normalization import parse_price

IN_STOCK = {"instock", "limitedavailability", "onlineonly", "instoreonly"}
NOT_PAYABLE_HINTS = re.compile(r"\b(emi|per month|/month|monthly|subscription|installment|no cost emi)\b", re.I)
_GTIN_KEYS = ("gtin", "gtin14", "gtin13", "gtin12", "gtin8", "isbn")


def _as_list(x: Any) -> list[Any]:
    return x if isinstance(x, list) else [] if x is None else [x]


def _has_type(node: dict, name: str) -> bool:
    return name in [str(t) for t in _as_list(node.get("@type"))]


def _walk(node: Any):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def extract_jsonld_products(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    found = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or tag.get_text() or "")
        except ValueError:
            continue
        for node in _walk(data):
            if _has_type(node, "Product") or _has_type(node, "ProductGroup"):
                found.append(node)
    return found


def _name(x: Any) -> str | None:
    if isinstance(x, dict):
        return x.get("name")
    return str(x) if x else None


def _pick_offer(prod: dict) -> dict | None:
    flat: list[dict] = []
    for o in _as_list(prod.get("offers")):
        if not isinstance(o, dict):
            continue
        inner = [x for x in _as_list(o.get("offers")) if isinstance(x, dict)]
        if _has_type(o, "AggregateOffer") and inner:
            flat.extend(inner)
        else:
            flat.append(o)
    return flat[0] if flat else None


def parse_product_page(html: str, url: str, retailer_product_id: str | None = None) -> ScrapedProduct:
    products = extract_jsonld_products(html)
    soup = BeautifulSoup(html, "lxml")

    def meta(prop: str) -> str | None:
        t = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
        return t.get("content") if t else None  # type: ignore[return-value]

    if products:
        prod = products[0]
        offer = _pick_offer(prod) or {}
        price = parse_price(offer.get("price") if offer.get("price") is not None else offer.get("lowPrice"))
        currency = (offer.get("priceCurrency") or "INR").upper()
        avail = str(offer.get("availability", "")).rsplit("/", 1)[-1].lower()
        in_stock = avail in IN_STOCK if avail else price is not None
        cond = str(offer.get("itemCondition", "")).rsplit("/", 1)[-1].lower()
        condition = "refurbished" if "refurb" in cond else "used" if "used" in cond else None
        offer_text = " ".join(str(offer.get(k, "")) for k in ("name", "description"))
        spec = offer.get("priceSpecification")
        for sp in _as_list(spec):
            if isinstance(sp, dict):
                offer_text += " " + str(sp.get("name", "")) + " " + str(sp.get("billingDuration", ""))
        mrp = None
        for sp in _as_list(spec):
            if isinstance(sp, dict) and re.search(r"list|strike|mrp", str(sp.get("priceType", "")), re.I):
                mrp = parse_price(sp.get("price"))
        agg = prod.get("aggregateRating") or {}
        rating = parse_price(agg.get("ratingValue")) if isinstance(agg, dict) else None
        reviews = None
        if isinstance(agg, dict):
            rc = agg.get("reviewCount") or agg.get("ratingCount")
            reviews = int(parse_price(rc) or 0) or None
        gtin = next((str(prod[k]) for k in _GTIN_KEYS if prod.get(k)), None)
        image: Any = prod.get("image")
        image = image[0] if isinstance(image, list) and image else image
        if isinstance(image, dict):
            image = image.get("url")
        sku = prod.get("sku") or prod.get("productID")
        title = prod.get("name")
        brand = _name(prod.get("brand"))
        seller = _name(offer.get("seller"))
        model = prod.get("model")
        model = _name(model) if model else None
        mpn = prod.get("mpn")
        category = prod.get("category")
    else:
        title = meta("og:title")
        price = parse_price(meta("product:price:amount") or meta("og:price:amount"))
        currency = (meta("product:price:currency") or meta("og:price:currency") or "INR").upper()
        avail = (meta("product:availability") or meta("og:availability") or "").lower()
        in_stock = ("in stock" in avail or avail == "instock") if avail else price is not None
        rating = reviews = gtin = seller = model = mpn = category = sku = mrp = None
        brand = meta("product:brand")
        image = meta("og:image")
        offer_text, condition = "", None

    if not title or price is None:
        raise ParseError("no structured product data (JSON-LD/OpenGraph) with title and price on page")
    rid = retailer_product_id or (str(sku) if sku else None)
    if not rid:
        raise ParseError("could not determine retailer product id")
    return ScrapedProduct(
        retailer_product_id=rid, url=url, title=str(title).strip(), price=price, currency=currency,
        in_stock=bool(in_stock), rating=rating, review_count=reviews, brand=brand, model=model,
        mpn=str(mpn) if mpn else None, gtin=gtin, category=category if isinstance(category, str) else None,
        seller=seller, image_url=urljoin(url, image) if isinstance(image, str) else None, mrp=mrp,
        payable=not NOT_PAYABLE_HINTS.search(offer_text), condition=condition,
    )


def extract_links(html: str, base_url: str, pattern: re.Pattern[str], limit: int = 100) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    seen: dict[str, None] = {}
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, str(a["href"])).split("#")[0].split("?")[0]
        if pattern.search(href):
            seen.setdefault(href, None)
            if len(seen) >= limit:
                break
    return list(seen)


def parse_sitemap(xml: str) -> tuple[list[str], list[str]]:
    """Returns (child_sitemaps, page_urls)."""
    soup = BeautifulSoup(xml, "xml")
    children = [loc.get_text(strip=True) for sm in soup.find_all("sitemap") for loc in sm.find_all("loc")]
    pages = [loc.get_text(strip=True) for u in soup.find_all("url") for loc in u.find_all("loc")]
    return children, pages
