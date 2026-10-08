"""Application settings, read from environment variables / .env (never hardcode secrets)."""
from __future__ import annotations

import json
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()

HISTORY_QUALITY_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


def _alias(*names: str) -> AliasChoices:
    return AliasChoices(*names)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg2://deals:deals@localhost:5432/deals"
    redis_url: str = "redis://localhost:6379/0"

    # --- Slack (credentials come from the environment only) ---
    slack_webhook_url: str | None = None
    slack_bot_token: str | None = None
    slack_channel_id: str | None = None
    # JSON map of category -> Slack channel id (bot token only), e.g. {"fashion": "C123"}
    slack_channel_map: str = ""
    notification_channels: str = "slack"

    # --- Deal thresholds ---
    min_rating: float = Field(4.0, validation_alias=_alias("MIN_RATING", "ALERT_MIN_RATING"))
    min_review_count: int = Field(20, validation_alias=_alias("MIN_REVIEW_COUNT", "ALERT_MIN_REVIEWS"))
    min_discount_percent: float = Field(
        50.0, validation_alias=_alias("MIN_DISCOUNT_PERCENT", "ALERT_MIN_DISCOUNT")
    )
    max_plausible_discount: float = 92.0  # beyond this we suspect a pricing error, not a deal
    min_history_quality: str = "MEDIUM"
    min_observations: int = 10
    min_match_confidence_for_deals: float = 80.0
    price_freshness_hours: int = 48
    allow_imported_history: bool = True

    # --- Alert de-duplication ---
    alert_renotify_after_hours: int = 24
    alert_material_change_percent: float = 5.0
    alert_reappear_days: int = 7
    deal_miss_tolerance: int = 2

    # --- Scheduling ---
    crawl_interval_minutes: int = 60  # hot products
    general_crawl_interval_minutes: int = 360
    discovery_interval_hours: int = 24
    scheduler_tick_minutes: int = 10
    crawl_batch_size: int = 500
    discovery_queries_per_run: int = 40
    discovery_results_per_query: int = 20
    heartbeat_hours: int = 6  # re-record unchanged price at most this often
    retention_days: int = 730

    # --- HTTP / crawling ---
    user_agent: str = "DealEngineBot/1.0 (+https://example.invalid/bot; price-monitoring)"
    http_timeout_seconds: float = 20.0
    per_domain_min_interval_seconds: float = 3.0
    respect_robots: bool = True
    page_cache_ttl_seconds: int = 600
    retailer_block_cooldown_hours: int = 6
    retailer_failure_threshold: int = 5
    browser_enabled: bool = False
    debug_dir: str = "debug"
    config_dir: str = "config"

    # --- FX ---
    fx_provider_url: str = "https://api.frankfurter.app/latest"
    fx_cache_ttl_hours: int = 12
    fx_fallback_rates: str = ""  # JSON {"USD": 83.1} (INR per unit), used only if provider is down

    # --- Retailer toggles ---
    enable_amazon: bool = True
    enable_flipkart: bool = True
    enable_myntra: bool = True
    enable_croma: bool = True
    enable_reliance_digital: bool = True
    enable_tata_cliq: bool = True
    enable_ajio: bool = True
    enable_nykaa: bool = True
    enable_meesho: bool = True
    enable_vijay_sales: bool = True
    enable_pepperfry: bool = True
    enable_ikea: bool = True
    enable_firstcry: bool = True
    enable_decathlon: bool = True

    # --- Official API credentials ---
    amazon_paapi_access_key: str | None = None
    amazon_paapi_secret_key: str | None = None
    amazon_paapi_partner_tag: str | None = None
    amazon_paapi_host: str = "webservices.amazon.in"
    amazon_paapi_region: str = "eu-west-1"
    flipkart_affiliate_id: str | None = None
    flipkart_affiliate_token: str | None = None

    def retailer_enabled(self, key: str) -> bool:
        return bool(getattr(self, f"enable_{key}", False))

    @property
    def channel_map(self) -> dict[str, str]:
        if not self.slack_channel_map:
            return {}
        try:
            data = json.loads(self.slack_channel_map)
            return {str(k): str(v) for k, v in data.items()}
        except (ValueError, AttributeError):
            return {}

    @property
    def fallback_rates(self) -> dict[str, float]:
        if not self.fx_fallback_rates:
            return {}
        try:
            return {str(k).upper(): float(v) for k, v in json.loads(self.fx_fallback_rates).items()}
        except (ValueError, AttributeError):
            return {}

    @property
    def channels(self) -> list[str]:
        return [c.strip() for c in self.notification_channels.split(",") if c.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
