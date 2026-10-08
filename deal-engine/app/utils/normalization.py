"""Title/attribute normalisation used by the product-matching engine.

Everything here is deterministic and conservative: when an attribute cannot be parsed it is left
out (None), and the matcher treats "unknown" differently from "different".
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

BRANDS = {
    "apple", "samsung", "sony", "lg", "oneplus", "xiaomi", "redmi", "poco", "realme", "oppo", "vivo",
    "motorola", "nokia", "google", "nothing", "iqoo", "asus", "acer", "dell", "hp", "lenovo", "msi",
    "boat", "jbl", "bose", "sennheiser", "noise", "fire-boltt", "amazfit", "garmin", "fitbit",
    "canon", "nikon", "gopro", "panasonic", "philips", "whirlpool", "godrej", "haier", "voltas",
    "bosch", "ifb", "prestige", "butterfly", "bajaj", "havells", "usha", "pigeon", "morphy richards",
    "nike", "adidas", "puma", "reebok", "skechers", "levis", "levi's", "wrangler", "h&m", "zara",
    "fila", "asics", "new balance", "under armour", "woodland", "bata", "crocs", "titan", "fastrack",
    "casio", "fossil", "maybelline", "lakme", "loreal", "l'oreal", "mamaearth", "nivea", "dove",
    "the ordinary", "cetaphil", "neutrogena", "minimalist", "ikea", "sleepwell", "wakefit",
    "kurlon", "nilkamal", "durian", "pampers", "huggies", "himalaya", "johnson", "chicco", "fisher-price",
    "lego", "hot wheels", "decathlon", "domyos", "kalenji", "quechua", "nivia", "cosco", "yonex",
    "microsoft", "nintendo", "sandisk", "seagate", "wd", "tp-link", "d-link", "netgear", "benq",
}
BRAND_ALIASES = {"levi's": "levis", "l'oreal": "loreal", "h&m": "hm", "redmi": "xiaomi redmi", "tp-link": "tplink"}

COLORS = {
    "black", "white", "blue", "red", "green", "yellow", "pink", "purple", "grey", "gray", "silver",
    "gold", "orange", "brown", "beige", "navy", "maroon", "teal", "titanium", "graphite", "midnight",
    "starlight", "lavender", "cream", "olive", "violet", "rose", "bronze", "copper", "charcoal",
    "mint", "lilac", "cyan", "magenta", "ivory", "khaki", "turquoise",
}
VARIANT_WORDS = {"pro", "max", "plus", "ultra", "mini", "lite", "se", "fe", "neo", "gt", "air", "prime", "elite", "turbo"}
STOPWORDS = {
    "with", "for", "and", "the", "of", "in", "a", "an", "new", "latest", "free", "buy", "online",
    "india", "by", "to", "from", "only", "upto", "up", "on", "at", "ram", "storage", "ssd", "hdd",
    "refurbished", "renewed", "used", "combo", "bundle", "pack", "set", "inch", "inches", "cm",
    "tv", "smartphone", "phone", "mobile", "laptop", "headphones", "earbuds", "generation", "gen",
}
SIZE_TOKENS = r"(?:xxs|xs|s|m|l|xl|xxl|xxxl|2xl|3xl|4xl)"
_UNIT_TOKEN = re.compile(
    r"^\d+(?:\.\d+)?(?:gb|tb|mb|inch|inches|in|hz|mah|w|mp|ml|l|kg|g|cm|mm|pcs|pack|gen|k|p|nm|v|a|th|st|nd|rd|x)$"
)
_NOT_MODEL = {"usb-c", "type-c", "wi-fi", "wifi6", "wifi7", "5g", "4g", "3g", "e-sim"}


def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text).lower()
    text = text.replace("&", " and ").replace("’", "'")
    text = re.sub(r"[^\w\s'\-\.\"]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_gtin(value: str | None) -> str | None:
    """Returns a 14-digit zero-padded GTIN if the check digit validates, else None."""
    if not value:
        return None
    digits = re.sub(r"\D", "", str(value))
    if len(digits) not in (8, 12, 13, 14):
        return None
    body, check = digits[:-1], int(digits[-1])
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    if (10 - total % 10) % 10 != check:
        return None
    return digits.zfill(14)


def normalize_mpn(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"[^a-z0-9]", "", value.lower())
    return cleaned if len(cleaned) >= 4 else None


def normalize_brand(value: str | None) -> str | None:
    if not value:
        return None
    b = normalize_text(value)
    b = re.sub(r"\b(official|store|india|pvt|ltd|limited)\b", "", b).strip()
    b = BRAND_ALIASES.get(b, b)
    return b.replace(" ", "") or None


def extract_brand(title: str, hint: str | None = None) -> str | None:
    if hint:
        return normalize_brand(hint)
    norm = normalize_text(title)
    best: tuple[int, int, str] | None = None
    for brand in BRANDS:
        m = re.search(rf"(?<![a-z0-9]){re.escape(brand)}(?![a-z0-9])", norm)
        if m:
            cand = (m.start(), -len(brand), brand)  # earliest mention wins, then longest
            if best is None or cand < best:
                best = cand
    return normalize_brand(best[2]) if best else None


def parse_price(text: str | float | int | None) -> float | None:
    """'₹1,29,999.00' -> 129999.0. Returns None if no number is present."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        return float(text)
    m = re.search(r"\d[\d.,]*", str(text))
    if not m:
        return None
    cleaned = m.group(0).rstrip(".,")
    if "," in cleaned and "." in cleaned and cleaned.rfind(",") > cleaned.rfind("."):
        cleaned = cleaned.replace(".", "").replace(",", ".")  # European 1.299,00
    else:
        cleaned = cleaned.replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


@dataclass
class Attributes:
    storage_gb: int | None = None
    ram_gb: int | None = None
    screen_in: float | None = None
    colors: frozenset[str] = field(default_factory=frozenset)
    pack: int = 1
    pack_explicit: bool = False
    generation: int | None = None
    connector: str | None = None
    size: str | None = None
    condition: str | None = None  # None == new
    bundle: bool = False
    variant_words: frozenset[str] = field(default_factory=frozenset)
    model_tokens: frozenset[str] = field(default_factory=frozenset)

    def to_dict(self) -> dict:
        return {
            "storage_gb": self.storage_gb, "ram_gb": self.ram_gb, "screen_in": self.screen_in,
            "colors": sorted(self.colors), "pack": self.pack, "generation": self.generation,
            "connector": self.connector, "size": self.size, "condition": self.condition,
            "bundle": self.bundle, "variant_words": sorted(self.variant_words),
            "model_tokens": sorted(self.model_tokens),
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> Attributes:
        d = d or {}
        return cls(
            storage_gb=d.get("storage_gb"), ram_gb=d.get("ram_gb"), screen_in=d.get("screen_in"),
            colors=frozenset(d.get("colors") or []), pack=d.get("pack") or 1,
            pack_explicit=bool(d.get("pack") and d.get("pack") != 1),
            generation=d.get("generation"), connector=d.get("connector"), size=d.get("size"),
            condition=d.get("condition"), bundle=bool(d.get("bundle")),
            variant_words=frozenset(d.get("variant_words") or []),
            model_tokens=frozenset(d.get("model_tokens") or []),
        )


_MEM = re.compile(r"(\d{1,4})\s?(gb|tb)\b(?:\s*(ram|memory))?")


def _parse_memory(norm: str) -> tuple[int | None, int | None]:
    storage: list[int] = []
    ram: list[int] = []
    for m in _MEM.finditer(norm):
        value = int(m.group(1)) * (1024 if m.group(2) == "tb" else 1)
        pre = norm[: m.start()]
        after = norm[m.end(): m.end() + 12]
        if m.group(3) or re.match(r"\s*(ram|memory|ddr)", after):
            ram.append(value)
        elif re.match(r"\s*(ssd|hdd|storage|rom|emmc|nvme|internal)", after):
            storage.append(value)
        elif re.search(r"ram[\s:]*$", pre) and not re.search(r"\d\s?(gb|tb)\s*ram[\s:]*$", pre):
            ram.append(value)
        else:
            storage.append(value)
    if len(storage) >= 2:  # "8GB/128GB": smaller one is RAM
        storage.sort()
        if storage[0] <= 24 and not ram:
            ram.append(storage.pop(0))
    return (max(storage) if storage else None, max(ram) if ram else None)


def parse_attributes(title: str, variant: str | None = None, model_hint: str | None = None) -> Attributes:
    raw = f"{title or ''} {variant or ''}"
    norm = normalize_text(raw)
    a = Attributes()
    a.storage_gb, a.ram_gb = _parse_memory(norm)

    m = re.search(r"(\d{2,3}(?:\.\d)?)[\s-]?(?:inch|inches|in\b|\")", norm)
    if m:
        a.screen_in = float(m.group(1))

    words = set(re.findall(r"[a-z]+", norm))
    a.colors = frozenset(words & COLORS)
    a.variant_words = frozenset(words & VARIANT_WORDS)

    pack = None
    for pat in (r"pack of (\d+)", r"set of (\d+)", r"combo of (\d+)", r"(\d+)\s?(?:-)?\s?(?:pack|pcs|pieces|pc|units?)\b", r"(\d+)\s?x\s?\d+\s?(?:ml|g|gm|kg|l)\b"):
        pm = re.search(pat, norm)
        if pm and 1 < int(pm.group(1)) <= 500:
            pack = int(pm.group(1))
            break
    if pack:
        a.pack, a.pack_explicit = pack, True
    a.bundle = bool(re.search(r"\b(combo|bundle|bundled)\b", norm))

    gm = (re.search(r"\b(\d)(?:st|nd|rd|th)[\s-]?gen(?:eration)?", norm)
          or re.search(r"\bgen(?:eration)?[\s-]?(\d)\b", norm)
          or re.search(r"\b(\d)[\s-]?gen\b", norm))
    if gm:
        a.generation = int(gm.group(1))

    if re.search(r"usb[\s-]?c|type[\s-]?c", norm):
        a.connector = "usbc"
    elif "lightning" in norm:
        a.connector = "lightning"
    elif re.search(r"micro[\s-]?usb", norm):
        a.connector = "microusb"

    sm = (re.search(rf"\bsize[\s:\-]*({SIZE_TOKENS})\b", norm)
          or re.search(rf"[,(\-]\s*({SIZE_TOKENS})\s*\)?\s*$", norm)
          or re.search(r"\b(?:size|uk|us|eu)[\s:\-]*(\d{1,2}(?:\.\d)?)\b", norm))
    if sm:
        a.size = sm.group(1)

    cm = re.search(r"\b(refurbished|renewed|pre[\s-]?owned|used|open[\s-]?box|second[\s-]?hand)\b", norm)
    if cm:
        a.condition = "refurbished" if cm.group(1) in ("refurbished", "renewed") else "used"

    tokens = set(_model_tokens(norm))
    if model_hint:
        tokens |= set(_model_tokens(normalize_text(model_hint)))
        mh = re.sub(r"[^a-z0-9]", "", model_hint.lower())
        if len(mh) >= 3 and re.search(r"\d", mh) and re.search(r"[a-z]", mh):
            tokens.add(mh)
    a.model_tokens = frozenset(tokens)
    return a


def _model_tokens(norm: str) -> list[str]:
    out = []
    for tok in re.findall(r"[a-z0-9][a-z0-9\-]*[a-z0-9]", norm):
        if tok in _NOT_MODEL or _UNIT_TOKEN.match(tok):
            continue
        if re.search(r"\d", tok) and re.search(r"[a-z]", tok) and len(tok.replace("-", "")) >= 3:
            out.append(tok.replace("-", ""))
    return out


def core_tokens(title: str, brand: str | None = None) -> frozenset[str]:
    """Descriptive tokens left after removing brand, colours, units and marketing filler."""
    norm = normalize_text(title)
    norm = _MEM.sub(" ", norm)
    norm = re.sub(r"\d{2,3}(?:\.\d)?[\s-]?(?:inch|inches|in\b|\")", " ", norm)
    norm = re.sub(r"(?:pack|set|combo) of \d+|\d+\s?(?:pack|pcs|pieces|pc)\b", " ", norm)
    norm = re.sub(r"\b\d+(?:st|nd|rd|th)[\s-]?gen(?:eration)?\b", " ", norm)
    brand_words = set((brand or "").split()) | ({brand} if brand else set())
    out = set()
    for tok in re.findall(r"[a-z0-9]+", norm):
        if tok in STOPWORDS or tok in COLORS or tok in brand_words:
            continue
        if re.fullmatch(r"(usb|type|c|lightning)", tok):
            continue
        out.add(tok)
    return frozenset(out)
