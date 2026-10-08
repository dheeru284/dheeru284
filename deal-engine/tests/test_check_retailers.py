import yaml

from app.config.settings import Settings
from app.crawlers import registry
from app.crawlers.public import PublicPageAdapter
from scripts.check_retailers import probe


def test_probe_reports_works_blocked_and_unconfigured(server, tmp_path):
    cls = lambda key: type(key, (PublicPageAdapter,), {"key": key, "name": key, "domain": server.domain, "scheme": "http",  # noqa: E731
                                                       "product_url_re": r"/p/(?P<id>\w+)", "search_url": None})
    registry.load_all()
    registry.ADAPTERS.update({"probe_ok": cls("probe_ok"), "probe_blocked": cls("probe_blocked"),
                              "probe_none": cls("probe_none")})
    base = f"http://{server.domain}"
    server.prices["/p/101"] = {"name": "Thing X1", "price": 100}
    server.blocked_paths.add("/p/202")
    (tmp_path / "seed_urls.yaml").write_text(yaml.safe_dump({"probe_ok": [f"{base}/p/101"],
                                                             "probe_blocked": [f"{base}/p/202"]}))
    s = Settings(_env_file=None, config_dir=str(tmp_path), per_domain_min_interval_seconds=0,
                 page_cache_ttl_seconds=0, redis_url="redis://localhost:6399/0")
    assert probe("probe_ok", s)["verdict"] == "WORKS"
    assert probe("probe_blocked", s)["verdict"].startswith("BLOCKED")
    assert probe("probe_none", s)["verdict"].startswith("UNTESTED")
    assert probe("amazon", s)["verdict"].startswith("UNCONFIGURED")
