"""Cross-retailer product matching.

Priority: GTIN > MPN > brand+model > normalised title (+attributes, +image hash as a small bonus).
Hard attribute conflicts (storage, colour, pack size, generation, connector, size, condition, model,
variant words such as Pro/Max) force the score to 0 - similar-looking titles are never merged.

Score bands: 90-100 exact, 80-89 strong, 70-79 possible, <70 no match.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from rapidfuzz import fuzz

from app.utils.normalization import (
    Attributes,
    core_tokens,
    extract_brand,
    normalize_gtin,
    normalize_mpn,
    parse_attributes,
)

AUTO_MERGE_THRESHOLD = 80.0
POSSIBLE_THRESHOLD = 70.0


@dataclass
class Features:
    title: str
    brand: str | None
    gtin: str | None
    mpn: str | None
    attrs: Attributes
    core: frozenset[str]
    image_hash: str | None = None

    @classmethod
    def build(cls, title: str, brand: str | None = None, gtin: str | None = None, mpn: str | None = None,
              variant: str | None = None, model: str | None = None, image_hash: str | None = None) -> Features:
        b = extract_brand(title, brand)
        return cls(
            title=title, brand=b, gtin=normalize_gtin(gtin), mpn=normalize_mpn(mpn),
            attrs=parse_attributes(title, variant, model), core=core_tokens(title, b), image_hash=image_hash,
        )


@dataclass
class MatchResult:
    score: float
    reasons: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)

    @property
    def band(self) -> str:
        if self.score >= 90:
            return "exact"
        if self.score >= AUTO_MERGE_THRESHOLD:
            return "strong"
        if self.score >= POSSIBLE_THRESHOLD:
            return "possible"
        return "none"


def image_similarity(h1: str | None, h2: str | None) -> float | None:
    """Similarity (0-1) of two hex perceptual hashes; None if unavailable."""
    if not h1 or not h2 or len(h1) != len(h2):
        return None
    try:
        dist = bin(int(h1, 16) ^ int(h2, 16)).count("1")
    except ValueError:
        return None
    return 1.0 - dist / (len(h1) * 4)


def compute_dhash(image_bytes: bytes) -> str | None:
    """64-bit difference hash (hex). Optional helper; requires Pillow."""
    try:
        import io

        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("L").resize((9, 8))
        px = list(img.getdata())
        bits = 0
        for row in range(8):
            for col in range(8):
                bits = (bits << 1) | (px[row * 9 + col] > px[row * 9 + col + 1])
        return f"{bits:016x}"
    except Exception:
        return None


def _conflicts(a: Attributes, b: Attributes) -> list[str]:
    out: list[str] = []
    for name in ("storage_gb", "ram_gb", "screen_in", "generation", "connector", "size"):
        va, vb = getattr(a, name), getattr(b, name)
        if va is not None and vb is not None and va != vb:
            out.append(f"{name}:{va}!={vb}")
    if a.pack != b.pack:
        out.append(f"pack:{a.pack}!={b.pack}")
    if a.colors and b.colors and not (a.colors & b.colors):
        out.append(f"color:{sorted(a.colors)}!={sorted(b.colors)}")
    if a.condition != b.condition:
        out.append(f"condition:{a.condition}!={b.condition}")
    if a.bundle != b.bundle:
        out.append("bundle_mismatch")
    if a.variant_words != b.variant_words:
        out.append(f"variant_words:{sorted(a.variant_words)}!={sorted(b.variant_words)}")
    if a.model_tokens and b.model_tokens and not (a.model_tokens & b.model_tokens):
        out.append(f"model:{sorted(a.model_tokens)}!={sorted(b.model_tokens)}")
    return out


def _agreeing_attrs(a: Attributes, b: Attributes) -> int:
    n = 0
    for name in ("storage_gb", "ram_gb", "screen_in", "generation", "connector", "size"):
        va, vb = getattr(a, name), getattr(b, name)
        if va is not None and va == vb:
            n += 1
    if a.colors and a.colors & b.colors:
        n += 1
    if a.pack_explicit and a.pack == b.pack:
        n += 1
    return n


def _asymmetry(a: Attributes, b: Attributes) -> int:
    """Count of key variant attributes present on exactly one side (cannot confirm same variant)."""
    n = 0
    for name in ("storage_gb", "ram_gb", "generation", "connector", "size", "screen_in"):
        if (getattr(a, name) is None) != (getattr(b, name) is None):
            n += 1
    return n


def match_score(a: Features, b: Features) -> MatchResult:
    if a.gtin and b.gtin:
        if a.gtin != b.gtin:
            return MatchResult(0.0, conflicts=["gtin_mismatch"])
        return MatchResult(100.0, reasons=["gtin_equal"])

    conflicts = _conflicts(a.attrs, b.attrs)
    if a.brand and b.brand and a.brand != b.brand:
        conflicts.append(f"brand:{a.brand}!={b.brand}")
    if conflicts:
        return MatchResult(0.0, conflicts=conflicts)

    reasons: list[str] = []
    agree = _agreeing_attrs(a.attrs, b.attrs)
    asym = _asymmetry(a.attrs, b.attrs)
    img = image_similarity(a.image_hash, b.image_hash)
    img_bonus = 4.0 if img is not None and img >= 0.9 else 0.0

    if a.mpn and b.mpn and a.mpn == b.mpn:
        reasons.append("mpn_equal")
        return MatchResult(min(99.0, 96.0 + img_bonus / 2), reasons)

    if not (a.brand and b.brand):
        # Without a confirmed brand on both sides we never exceed "no auto-merge".
        ratio = fuzz.token_set_ratio(a.title.lower(), b.title.lower())
        return MatchResult(min(65.0, ratio * 0.65), ["title_only_no_brand"])

    shared_models = a.attrs.model_tokens & b.attrs.model_tokens
    jaccard = len(a.core & b.core) / len(a.core | b.core) if (a.core | b.core) else 0.0

    if shared_models:
        reasons.append(f"brand+model:{sorted(shared_models)}")
        score = 88.0 + min(8.0, 2.0 * agree) + (4.0 if jaccard >= 0.6 else 0.0) + img_bonus
        if asym:  # one side lacks a variant attribute: cannot confirm same variant -> never auto-merge
            reasons.append("variant_attr_missing_on_one_side")
            score = min(score, 75.0)
        return MatchResult(max(0.0, min(99.0, score)), reasons)

    if not a.attrs.model_tokens and not b.attrs.model_tokens and jaccard == 1.0 and len(a.core) >= 3:
        reasons.append("brand+identical_core_title")
        score = 80.0 + min(8.0, 2.0 * agree) + img_bonus
        if asym:
            score = min(score, 75.0)
        return MatchResult(max(0.0, min(89.0, score)), reasons)

    if jaccard >= 0.8:
        reasons.append("brand+similar_title")
        return MatchResult(min(79.0, 60.0 + 20.0 * jaccard - 5.0 * asym + img_bonus), reasons)

    ratio = fuzz.token_set_ratio(a.title.lower(), b.title.lower())
    return MatchResult(min(65.0, ratio * 0.65), ["fuzzy_title_only"])


def product_features(product) -> Features:  # type: ignore[no-untyped-def]
    """Rebuild Features from a canonical Product row."""
    return Features(
        title=product.canonical_name, brand=product.brand, gtin=product.gtin,
        mpn=normalize_mpn(product.manufacturer_part_number),
        attrs=Attributes.from_dict(product.normalized_attributes),
        core=frozenset(product.core_tokens or []), image_hash=product.image_hash,
    )


def find_best_match(candidates, listing: Features, threshold: float = AUTO_MERGE_THRESHOLD):  # type: ignore[no-untyped-def]
    """Return (product, MatchResult, runners_up). `product` is None if nothing reaches `threshold`."""
    scored = []
    for prod in candidates:
        res = match_score(product_features(prod), listing)
        scored.append((res.score, prod.id, prod, res))
    scored.sort(key=lambda t: (-t[0], t[1]))
    if not scored:
        return None, MatchResult(0.0, ["no_candidates"]), []
    best_score, _, best_prod, best_res = scored[0]
    runners = [{"product_id": p.id, "score": round(s, 1)} for s, _, p, _ in scored[1:4] if s >= POSSIBLE_THRESHOLD]
    if best_score >= threshold:
        return best_prod, best_res, runners
    possible = [{"product_id": p.id, "score": round(s, 1)} for s, _, p, _ in scored[:3] if s >= POSSIBLE_THRESHOLD]
    return None, best_res, possible
