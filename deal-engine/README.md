# Deal Engine — historical-price deal alerts for Indian e-commerce

Continuously records prices from Indian retailers, builds a price history **from what it actually observed**,
matches the same product across retailers, and posts to Slack only when the best current price is
≥ 50 % below a credible historical baseline. **MRP / strike-through prices are stored but never used as a baseline.**

## 0. Read this first — what is and isn't proven

| Area | Status |
|---|---|
| History stats, deal rules, matching, de-dup, Slack payloads, FX, pricing rules | **Verified** — 95 automated tests (SQLite *and* PostgreSQL), ruff + mypy clean |
| Full pipeline (discover → crawl → store → match → history → detect → de-dup → Slack) | **Verified** end-to-end through real Postgres 16, Redis, a Celery worker + Celery Beat and uvicorn, against a *local* fixture "retailer" and a local Slack receiver (`scripts/dev_fixture_shop.py`). The spec's own example (median ₹20,000, price ₹9,500 → 52.5 %) produced exactly one Slack message; later crawl cycles were suppressed as duplicates |
| `docker compose up -d` | `docker-compose.yml` passes `docker compose config`. **Not run** — the build sandbox has no Docker daemon. The same topology (postgres, redis, worker, beat, api) was run as plain processes |
| Real retailer sites | **Not verified.** The build sandbox's network allow-list blocks every retailer domain, so no adapter has been run against a live site. CSS/JSON-LD behaviour, URL patterns and robots.txt rules of the 12 public-page adapters are best-effort and must be validated by you (see §9) |
| Amazon PA-API / Flipkart Affiliate adapters | Written from public documentation; request signing and response mapping are unit-tested with mocks, **never called live** |
| Slack against real Slack | Payload + both transports (webhook, `chat.postMessage`) tested with mocks and a local receiver, not against slack.com |

**Retailer access policy (deliberate).** The system does not scrape around anti-bot measures. Amazon's terms prohibit
scraping → Amazon uses the official PA-API only. Flipkart → Affiliate API only. Other retailers → public pages that
publish schema.org JSON-LD, fetched **only if robots.txt allows it**, throttled, honestly identified (`USER_AGENT`).
Any 401/403/429/CAPTCHA/robots refusal pauses that retailer for `RETAILER_BLOCK_COOLDOWN_HOURS` and the rest keep running;
there is no retry-with-different-headers, proxy rotation, or CAPTCHA handling. The most reliable route for most
retailers is a **permitted product feed** (affiliate networks) — set `FEED_<KEY>_URL` and the feed replaces page fetching.

**Known data limitations**
* PA-API 5 and Flipkart's v1 Affiliate payload return **no ratings**. Product rating is a review-count-weighted mean over *all matched listings that have one*; with no rated listing, no alert is sent (`rating_unknown`).
* A brand-new install **cannot alert for roughly the first 1–2 weeks** (needs ≥10 observations over ≥7 days and ≥5 distinct days for MEDIUM history). That is intentional (§42). Speed it up with legitimately obtained history via `scripts/import_history.py` (stored as `IMPORTED_HISTORY`, flagged in the alert).
* Title-only cross-site matching is conservative: listings without GTIN/MPN/model number often won't merge, which means fewer (never wrong) cross-retailer comparisons.

## 1. Architecture

```
Celery Beat ──► schedule_crawls (every SCHEDULER_TICK_MINUTES) ─┐
            ──► discover_all (daily) ──► discover_products ──────┤  queue: discovery
            ──► aggregate_history / cleanup / refresh_fx (daily) │
                                                                 ▼
                 crawl_product ──► store_price ──► detect_deals ──► send_slack_alert
                 (adapter fetch,    (listing upsert,   (history stats,   (Block Kit, per-channel
                  retries 30s→2m→10m  canonical match,  baseline, rules,   idempotent delivery)
                  circuit breaker)    price observation) de-dup state)
```

* `app/crawlers` – `RetailerAdapter` interface (`discover_products`, `search_products`, `fetch_product`, `fetch_price`, `fetch_rating`, `fetch_availability`, `fetch_reviews`), polite `Fetcher` (robots, throttle, cache, block detection), optional Playwright `BrowserFetcher`, JSON-LD parser, `PublicPageAdapter`, `FeedAdapter`, `AmazonAdapter` (PA-API), `FlipkartAdapter`, one module per retailer, registry.
* `app/services/product_matching.py` – GTIN › MPN › brand+model › normalised title (+attributes, +image hash bonus). Hard conflicts (storage, RAM, colour, pack size, generation, connector, size, condition, bundle, Pro/Max/Plus/…, model number) force score 0. Bands: 90–100 exact, 80–89 strong, 70–79 possible, <70 none; ≥80 auto-merges.
* `app/services/price_history.py` – statistics on **daily** prices (crawl frequency can't bias them): min/max/avg/median, 7/30/90/180/365-day averages, 30/90/180/lifetime medians, volatility, spike clipping, quality LOW/MEDIUM/HIGH.
* `app/services/deal_detector.py` – pure `decide()`; cross-retailer ranking; score; severity. `dedup.py` – alert state machine. `detection.py` – persists `DealEvent`s.
* `app/notifiers` – `Notifier` interface + registry; `SlackNotifier` (webhook or bot token, Block Kit).
* `app/api` – FastAPI: `/health /metrics /products /products/{id} /products/{id}/history /deals /retailers /stats` (+ `/docs`).
* Data: PostgreSQL (SQLAlchemy 2, Alembic). `price_observations` is append-only; `daily_prices` is the roll-up the engine reads; Redis = broker, page cache, cross-process throttle and metrics.

### How a deal is decided (all must hold)
1. At least one **eligible** offer: in stock, payable (not EMI-/subscription-only, not refurbished/used), observed within `PRICE_FRESHNESS_HOURS`, match confidence ≥ `MIN_MATCH_CONFIDENCE_FOR_DEALS` (80).
2. Rating ≥ `MIN_RATING` (4.0) and reviews ≥ `MIN_REVIEW_COUNT` (20) (set `MIN_REVIEW_COUNT=0` to disable).
3. History quality ≥ `MIN_HISTORY_QUALITY` (MEDIUM) and ≥ `MIN_OBSERVATIONS` (10) — otherwise `insufficient_history`.
4. **Baseline = the lowest credible median** of the 30/90/180-day/lifetime windows, using only history *before today* and only windows with enough distinct days. Taking the lowest means: a single price spike can't inflate it (medians), and a price that has been low for weeks is the new normal, not a drop.
5. Discount vs that baseline ≥ `MIN_DISCOUNT_PERCENT`, and also ≥ threshold vs the spike-clipped historical max. Above `MAX_PLAUSIBLE_DISCOUNT` (92 %) it is treated as a probable pricing error and not alerted.
6. Severity: ≥70 % EXTREME 🔥, ≥60 % GREAT 🚨, ≥50 % GOOD 🔥. The score (0–100: discount, history quality, rating/reviews, cross-retailer confirmation, stability, match confidence) is an **internal ranking signal**, not a truth claim.

Effective price = displayed price + shipping − coupon **only if the coupon is verified** (`ScrapedProduct.coupon_verified`). Displayed, coupon, membership and MRP values are all stored separately; membership price and MRP never enter deal maths.

**De-duplication** (per product, `alert_states`): alert once; re-alert only if ≥`ALERT_RENOTIFY_AFTER_HOURS` have passed **and** (price fell ≥`ALERT_MATERIAL_CHANGE_PERCENT`, or discount improved by that many points, or severity tier rose); or the deal disappeared for `DEAL_MISS_TOLERANCE` evaluations and came back; or ≥`ALERT_REAPPEAR_DAYS` since the last alert.

## 2. Requirements
Python 3.12+, PostgreSQL 14+, Redis 6+ (or just Docker + Compose). Optional: Chromium via Playwright (`BROWSER_ENABLED=true`) for JS-only pages, only where robots/ToS permit.

## 3. Installation (local)
```bash
cd deal-engine
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env        # then edit; for local services use localhost instead of the docker hostnames:
#   DATABASE_URL=postgresql+psycopg2://deals:deals@localhost:5432/deals
#   REDIS_URL=redis://localhost:6379/0
```

## 4. Configuration
Everything is an environment variable (see `.env.example`, all documented). Never commit `.env`.
Editable without code changes: `config/categories.yaml` (discovery keywords), `config/seed_urls.yaml` (curated product URLs per retailer), `config/retailers.yaml` (new public-page retailers).

## 5. Slack setup
*Webhook (simplest):* Slack → Apps → *Incoming Webhooks* → add to channel → `SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...`.
*Bot token:* create an app with `chat:write`, install, invite the bot to the channel → `SLACK_BOT_TOKEN=xoxb-...`, `SLACK_CHANNEL_ID=C0123...`. Optional per-category channels: `SLACK_CHANNEL_MAP={"fashion":"C0FASHION"}` (bot token only).
Secrets are read from the environment and redacted in logs. Test delivery without waiting for a real deal:
```bash
python - <<'EOF'
from tests.test_slack import payload
from app.notifiers.slack import SlackNotifier
SlackNotifier().send_deal(payload())   # sends a clearly-sample alert to your configured channel
EOF
```

## 6. Database setup
```bash
createdb deals    # or use the compose postgres
alembic upgrade head          # creates all tables
python -m scripts.seed        # registers retailers from the adapter registry (+ status: unconfigured/ok)
```
After changing models: `alembic revision --autogenerate -m "..." && alembic upgrade head` (`alembic check` should say "No new upgrade operations").

## 7. Running locally (4 processes)
```bash
uvicorn app.api.main:app --port 8000
celery -A app.workers.celery_app:celery worker -l info -Q default,crawl,discovery,alerts --concurrency 4
celery -A app.workers.celery_app:celery beat -l info
# first run: don't wait a day for the discovery schedule
python -c "from app.workers.discovery import discover_all; discover_all.delay()"
curl localhost:8000/health ; curl localhost:8000/retailers ; curl localhost:8000/stats
```
Smoke-test the whole pipeline against a local fake retailer (no real sites touched): `python -m scripts.dev_fixture_shop 8765`, then follow the setup in `tests/test_e2e_pipeline.py`.

## 8. Docker deployment
```bash
cp .env.example .env && $EDITOR .env      # set POSTGRES_PASSWORD, Slack, credentials/feeds
docker compose up -d --build
docker compose ps ; docker compose logs -f worker
curl localhost:8000/health
```
Services: `postgres`, `redis`, `migrate` (one-shot: alembic + seed), `app` (API :8000), `worker`, `scheduler` (Celery Beat). Add Chromium with `docker compose build --build-arg WITH_BROWSER=true` and `BROWSER_ENABLED=true`. API docs at `/docs`. There is no web UI; the API is the dashboard.

## 9. Making retailers work (do this before relying on alerts)
1. `curl localhost:8000/retailers` — `status` is `ok`, `degraded`, `unavailable` (blocked; `status_reason` says why and for how long) or `unconfigured` (missing credentials/feed).
2. **Amazon**: join Amazon Associates India, get PA-API keys → `AMAZON_PAAPI_ACCESS_KEY/SECRET_KEY/PARTNER_TAG`. **Flipkart**: Affiliate API → `FLIPKART_AFFILIATE_ID/TOKEN`.
3. **Everyone else**: preferably an affiliate/product feed → `FEED_CROMA_URL=...` (CSV/JSON/JSON-lines; remap columns with `FEED_CROMA_MAP='{"price":"sale_price","id":"sku"}'`). Otherwise add real product URLs to `config/seed_urls.yaml` and check the logs for `robots.txt disallows` / `blocked`. Verify the `search_url` / `product_url_re` constants in `app/crawlers/<retailer>.py` against the live site — they are unverified guesses.
4. Respect each site's Terms of Service; you are responsible for the retailers you enable (`ENABLE_<KEY>=false` turns one off).

## 10. Adding a retailer
*No code (public pages with JSON-LD):* add to `config/retailers.yaml` (template inside), restart.
*Code:* create `app/crawlers/<name>.py`:
```python
from app.crawlers.public import PublicPageAdapter   # or subclass RetailerAdapter for an API
from app.crawlers.registry import register

@register
class ShoppersStopAdapter(PublicPageAdapter):
    key, name, domain = "shoppers_stop", "Shoppers Stop", "www.shoppersstop.com"
    search_url = "https://www.shoppersstop.com/search?q={query}"
    product_url_re = r"/p/(?P<id>[\w-]+)"
    access_policy = "Public pages, robots.txt-gated."
```
add the module name to `_MODULES` in `app/crawlers/registry.py`, add `enable_shoppers_stop: bool = True` to `Settings` (or set `ENABLE_SHOPPERS_STOP`), run `python -m scripts.seed`. Core detection code is untouched.

## 11. Adding a category / notification channel / currency
* Category: add a key with keywords to `config/categories.yaml` (no restart of the DB needed; takes effect on the next discovery run).
* Channel (Email/Telegram/Discord/…): subclass `Notifier` in `app/notifiers/`, `@register_notifier`, import it in `app/notifiers/__init__.py`, set `NOTIFICATION_CHANNELS=slack,telegram`. Delivery status is tracked per (deal, channel).
* Currency: supported out of the box — INR, USD, AED, SGD, AUD, EUR, GBP, CAD, CHF, JPY (`app/utils/currency.py`). Rates come from `FX_PROVIDER_URL` (Frankfurter-compatible), cached in process memory and in the `exchange_rates` table for `FX_CACHE_TTL_HOURS`; if the provider is down the last stored rate is used, then `FX_FALLBACK_RATES`; with none, the price is **skipped** rather than recorded wrongly. Original currency and the INR value are both stored.

## 12. Thresholds
`MIN_DISCOUNT_PERCENT=50` (alias `ALERT_MIN_DISCOUNT`), `MIN_RATING=4.0` (`ALERT_MIN_RATING`), `MIN_REVIEW_COUNT=20` (`ALERT_MIN_REVIEWS`, `0` disables), `MIN_HISTORY_QUALITY=MEDIUM|HIGH`, `ALERT_RENOTIFY_AFTER_HOURS=24`. Lowering the discount threshold increases false positives; the history/baseline rules are what keep alerts genuine, so prefer tightening `MIN_HISTORY_QUALITY` over loosening them.

## 13. Troubleshooting
| Symptom | Check |
|---|---|
| No alerts at all | `GET /products/{id}` → `deal.reasons` explains exactly why (`insufficient_history`, `rating_unknown`, `discount_below_threshold`, …). Normal for the first ~2 weeks |
| Retailer `unavailable` | `/retailers` → `status_reason`; blocked by robots/403/429/CAPTCHA. It retries after the cooldown. Use the official API or a feed instead; don't work around the block |
| Retailer `unconfigured` | Add API credentials or `FEED_<KEY>_URL` |
| Slack alert `failed` | `/deals?notification_status=failed`; `notifications.error`; wrong channel/token. Failed alerts are retried by a 15-minute sweep for 24 h after detection |
| Listings not merging | `retailer_products.match_notes` shows reasons/possible matches; add GTIN/MPN via feed, or accept separate products |
| Worker idle | `celery -A app.workers.celery_app:celery inspect active`; make sure the worker listens to all four queues |
| `alembic check` reports drift | generate a migration (§6) |

## 14. Testing
```bash
pytest -q                                   # SQLite, ~20 s
TEST_DATABASE_URL=postgresql+psycopg2://deals:deals@localhost:5432/deals_test pytest -q   # real Postgres
ruff check . && mypy app
```
Covers: matching (exact/model/storage/colour/pack/generation/connector/brand/refurb), history (normal, 50 % drop, spike, outlier, insufficient, quality bands), detection (4.5★+55 % ✔, 3.8★+60 % ✘, 4.5★+40 % ✘, insufficient history ✘), cross-retailer best price, de-dup, Slack payload + transports, robots/403/CAPTCHA handling and per-retailer isolation, FX caching, coupon/membership/EMI handling, API endpoints, Celery task chain, and a full pipeline test with real HTTP.

## 15. Production notes
* Run ≥2 workers; scale `--concurrency` and add workers per queue (`crawl` is the heavy one). One `scheduler` instance only.
* Use managed Postgres with backups; `price_observations` is the system of record (older than `RETENTION_DAYS` is pruned, `daily_prices` roll-ups are kept). The schema is indexed for ~100k products × several retailers; crawl load is bounded by `CRAWL_BATCH_SIZE`, per-domain throttling, unchanged-price skipping (`HEARTBEAT_HOURS`) and hot/general intervals (`CRAWL_INTERVAL_MINUTES` / `GENERAL_CRAWL_INTERVAL_MINUTES`; products within 30 % of a deal and alerted products become "hot").
* Put the API behind your reverse proxy with authentication — it has none and exposes your catalogue.
* Scrape `/metrics` (Prometheus text; per-retailer `crawls_*`, `prices_recorded`, `deals_detected`, `slack_alerts_sent`, `duplicate_alerts_suppressed`, `retailer_blocked`). Logs are JSON, secrets redacted.
* Set a real contact in `USER_AGENT`.
* Throughput at 100k products has **not** been load-tested; design choices (daily roll-up, batched scheduling, Redis-backed throttle) are aimed at it, but measure before trusting it.
