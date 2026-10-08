import pytest

from app.services.product_matching import Features, match_score
from app.utils.normalization import normalize_gtin, parse_attributes


def score(t1, t2, **kw):
    a = Features.build(t1, **{k[:-2]: v for k, v in kw.items() if k.endswith("_a")})
    b = Features.build(t2, **{k[:-2]: v for k, v in kw.items() if k.endswith("_b")})
    return match_score(a, b)


def test_exact_product_different_wording_same_model():
    r = score("Sony WH-1000XM5 Wireless Noise Cancelling Headphones (Black)",
              "Sony WH-1000XM5 Over Ear Headphones, 30Hr Battery, Black")
    assert r.score >= 80, r


def test_gtin_match_is_exact():
    r = score("Foo Widget", "Totally different title", gtin_a="4006381333931", gtin_b="04006381333931")
    assert normalize_gtin("4006381333931") == "04006381333931"
    assert r.score == 100


def test_gtin_mismatch_is_not_a_match():
    r = score("Samsung Galaxy S23 128GB", "Samsung Galaxy S23 128GB", gtin_a="4006381333931", gtin_b="5012345678900")
    assert r.score == 0


def test_invalid_gtin_ignored():
    assert normalize_gtin("1234567890123") is None


def test_mpn_match():
    r = score("Samsung 55 inch TV", "Samsung Smart Television 55\"", mpn_a="QA55-Q60D", mpn_b="qa55q60d",
              brand_a="Samsung", brand_b="Samsung")
    assert r.score >= 90


def test_different_model_same_series():
    r = score("Samsung 55 inch QLED TV QN90C", "Samsung 55 inch QLED TV QN90D")
    assert r.score == 0 and any(c.startswith("model") for c in r.conflicts)


def test_different_storage():
    r = score("Samsung Galaxy S23 5G (8GB RAM, 128GB Storage)", "Samsung Galaxy S23 5G (8GB RAM, 256GB Storage)")
    assert r.score == 0 and any(c.startswith("storage") for c in r.conflicts)


def test_same_storage_different_phrasing_matches():
    r = score("Samsung Galaxy S23 5G (8GB RAM, 256GB Storage) Phantom Black",
              "Samsung Galaxy S23 5G 8GB/256GB Phantom Black")
    assert r.score >= 80, r


def test_different_color():
    r = score("Apple iPhone 15 128GB Black", "Apple iPhone 15 128GB Blue")
    assert r.score == 0 and any(c.startswith("color") for c in r.conflicts)


def test_different_pack_size():
    r = score("Dettol Handwash Refill Pack of 3", "Dettol Handwash Refill Pack of 1")
    assert r.score == 0 and any(c.startswith("pack") for c in r.conflicts)
    r2 = score("Maggi Noodles 12 pack", "Maggi Noodles")
    assert r2.score == 0


def test_different_generation():
    r = score("Apple AirPods Pro 2nd Generation", "Apple AirPods Pro 1st Generation")
    assert r.score == 0 and any(c.startswith("generation") for c in r.conflicts)


def test_airpods_usbc_vs_lightning():
    r = score("Apple AirPods Pro 2 USB-C", "Apple AirPods Pro 2 Lightning")
    assert r.score == 0 and any(c.startswith("connector") for c in r.conflicts)


def test_variant_words_pro_vs_base():
    assert score("Apple iPhone 15 128GB", "Apple iPhone 15 Pro 128GB").score == 0


def test_refurbished_never_matches_new():
    assert score("Apple iPhone 13 128GB Blue", "Apple iPhone 13 128GB Blue (Renewed)").score == 0


def test_different_brand():
    assert score("Sony XM5 Headphones", "Bose XM5 Headphones").score == 0


def test_similar_title_without_brand_never_auto_merges():
    r = score("Wireless bluetooth earbuds 40 hour battery", "Wireless bluetooth earbuds 40 hour battery case")
    assert r.score < 70


def test_apparel_size_conflict():
    r = score("Levis Men Slim Fit T-Shirt Size M", "Levis Men Slim Fit T-Shirt Size XXL")
    assert r.score == 0


def test_missing_storage_on_one_side_blocks_auto_merge():
    r = score("Samsung Galaxy S23 5G 256GB Black", "Samsung Galaxy S23 5G Black")
    assert r.score < 80


def test_parse_attributes():
    a = parse_attributes("Dell XPS 13 9330 Laptop 16GB RAM 1TB SSD 13.4 inch")
    assert a.ram_gb == 16 and a.storage_gb == 1024 and a.screen_in == 13.4 and "xps" not in a.model_tokens
    assert "9330" not in a.model_tokens


def test_image_hash_helpers():
    import io

    from PIL import Image

    from app.services.product_matching import compute_dhash, image_similarity

    def img(shade):
        im = Image.new("L", (64, 64), 0)
        for x in range(64):
            for y in range(64):
                im.putpixel((x, y), (x * shade) % 256)
        b = io.BytesIO()
        im.save(b, "PNG")
        return b.getvalue()

    h1, h2 = compute_dhash(img(3)), compute_dhash(img(3))
    assert image_similarity(h1, h2) == 1.0 and image_similarity(h1, None) is None
    assert compute_dhash(b"not an image") is None
    # image similarity can only nudge a title/model match, never create one
    a = Features.build("Sony XM5 Headphones", image_hash=h1)
    b = Features.build("Sony XM4 Headphones", image_hash=h1)
    assert match_score(a, b).score == 0
