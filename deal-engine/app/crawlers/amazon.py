"""Amazon India via the official Product Advertising API 5.0 (Amazon's terms prohibit scraping).

Requires an Associates account + PA-API credentials (AMAZON_PAAPI_*). Limitation: PA-API 5 does not
return customer ratings/review counts, so Amazon listings carry no rating; the deal engine takes
ratings from other matched retailers instead (or alerts are withheld if none is known).
NOTE: written against the public PA-API 5 documentation; not exercised against live credentials
in this repository's test-suite."""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone

import httpx

from app.config.settings import Settings, get_settings
from app.crawlers.base import (
    ParseError,
    ProductCandidate,
    ProductNotFound,
    RetailerAdapter,
    RetailerBlocked,
    RetailerError,
    RetailerNotConfigured,
    ScrapedProduct,
)
from app.crawlers.registry import register

RESOURCES = [
    "ItemInfo.Title", "ItemInfo.ByLineInfo", "ItemInfo.ExternalIds", "ItemInfo.ManufactureInfo",
    "ItemInfo.Classifications", "Offers.Listings.Price", "Offers.Listings.SavingBasis",
    "Offers.Listings.Availability.Type", "Offers.Listings.Condition", "Offers.Listings.MerchantInfo",
    "Images.Primary.Large",
]


def sign_v4(access: str, secret: str, region: str, host: str, path: str, target: str, body: str,
            now: datetime | None = None) -> dict[str, str]:
    now = now or datetime.now(timezone.utc)
    amz_date, date = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
    service = "ProductAdvertisingAPI"
    headers = {"content-encoding": "amz-1.0", "content-type": "application/json; charset=utf-8",
               "host": host, "x-amz-date": amz_date, "x-amz-target": target}
    signed = ";".join(sorted(headers))
    canon_headers = "".join(f"{k}:{headers[k]}\n" for k in sorted(headers))
    canon = "\n".join(["POST", path, "", canon_headers, signed, hashlib.sha256(body.encode()).hexdigest()])
    scope = f"{date}/{region}/{service}/aws4_request"
    to_sign = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canon.encode()).hexdigest()])

    def h(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode(), hashlib.sha256).digest()

    k = h(h(h(h(("AWS4" + secret).encode(), date), region), service), "aws4_request")
    sig = hmac.new(k, to_sign.encode(), hashlib.sha256).hexdigest()
    headers["Authorization"] = (f"AWS4-HMAC-SHA256 Credential={access}/{scope}, "
                                f"SignedHeaders={signed}, Signature={sig}")
    return headers


@register
class AmazonAdapter(RetailerAdapter):
    key, name, domain = "amazon", "Amazon India", "www.amazon.in"
    access_policy = ("Official PA-API 5 only (scraping prohibited by Amazon's terms). Needs AMAZON_PAAPI_* "
                     "credentials; no ratings available from the API.")

    def __init__(self, settings: Settings | None = None, client: httpx.Client | None = None):
        self.s = settings or get_settings()
        self.client = client or httpx.Client(timeout=self.s.http_timeout_seconds)

    def is_configured(self) -> bool:
        return bool(self.s.amazon_paapi_access_key and self.s.amazon_paapi_secret_key and self.s.amazon_paapi_partner_tag)

    def _call(self, op: str, payload: dict) -> dict:
        if not self.is_configured():
            raise RetailerNotConfigured("AMAZON_PAAPI_ACCESS_KEY / _SECRET_KEY / _PARTNER_TAG not set")
        payload = {**payload, "PartnerTag": self.s.amazon_paapi_partner_tag, "PartnerType": "Associates",
                   "Marketplace": "www.amazon.in", "Resources": RESOURCES}
        body = json.dumps(payload)
        host = self.s.amazon_paapi_host
        path = f"/paapi5/{op.lower()}"
        headers = sign_v4(self.s.amazon_paapi_access_key, self.s.amazon_paapi_secret_key,  # type: ignore[arg-type]
                          self.s.amazon_paapi_region, host, path,
                          f"com.amazon.paapi5.v1.ProductAdvertisingAPIv1.{op}", body)
        resp = self.client.post(f"https://{host}{path}", content=body, headers=headers)
        if resp.status_code in (401, 403):
            raise RetailerBlocked(f"PA-API rejected credentials/access: HTTP {resp.status_code}")
        if resp.status_code == 429:
            raise RetailerBlocked("PA-API throttled (HTTP 429); reduce request volume")
        if resp.status_code >= 400:
            raise RetailerError(f"PA-API HTTP {resp.status_code}: {resp.text[:200]}")
        return resp.json()

    @staticmethod
    def _item_to_product(item: dict) -> ScrapedProduct:
        info = item.get("ItemInfo", {})
        title = info.get("Title", {}).get("DisplayValue")
        listings = (item.get("Offers") or {}).get("Listings") or []
        if not title:
            raise ParseError("PA-API item without title")
        brand = (info.get("ByLineInfo", {}).get("Brand") or {}).get("DisplayValue")
        ext = info.get("ExternalIds", {})
        eans = (ext.get("EANs") or {}).get("DisplayValues") or (ext.get("UPCs") or {}).get("DisplayValues") or []
        man = info.get("ManufactureInfo", {})
        listing = listings[0] if listings else None
        price = listing["Price"]["Amount"] if listing and listing.get("Price") else None
        cond = ((listing or {}).get("Condition") or {}).get("Value", "New").lower()
        avail = ((listing or {}).get("Availability") or {}).get("Type", "")
        return ScrapedProduct(
            retailer_product_id=item["ASIN"], url=item["DetailPageURL"], title=title, price=price,
            currency=(listing or {}).get("Price", {}).get("Currency", "INR"),
            in_stock=bool(listing) and avail.lower() in ("now", ""),
            brand=brand, model=(man.get("Model") or {}).get("DisplayValue"),
            mpn=(man.get("ItemPartNumber") or {}).get("DisplayValue"), gtin=eans[0] if eans else None,
            category=(info.get("Classifications", {}).get("ProductGroup") or {}).get("DisplayValue"),
            seller=((listing or {}).get("MerchantInfo") or {}).get("Name"),
            image_url=(((item.get("Images") or {}).get("Primary") or {}).get("Large") or {}).get("URL"),
            mrp=((listing or {}).get("SavingBasis") or {}).get("Amount"),
            condition=None if cond == "new" else cond,
        )

    def search_products(self, query: str, limit: int = 10) -> list[ProductCandidate]:
        data = self._call("SearchItems", {"Keywords": query, "ItemCount": min(limit, 10), "SearchIndex": "All"})
        out = []
        for item in (data.get("SearchResult") or {}).get("Items", []):
            try:
                p = self._item_to_product(item)
            except (ParseError, KeyError):
                continue
            out.append(ProductCandidate(p.retailer_product_id, p.url, p.title, p.category, p))
        return out

    def fetch_product(self, url_or_id: str) -> ScrapedProduct:
        asin = url_or_id.rstrip("/").split("/dp/")[-1].split("/")[0].split("?")[0]
        data = self._call("GetItems", {"ItemIds": [asin]})
        items = (data.get("ItemsResult") or {}).get("Items") or []
        if not items:
            raise ProductNotFound(asin)
        return self._item_to_product(items[0])
