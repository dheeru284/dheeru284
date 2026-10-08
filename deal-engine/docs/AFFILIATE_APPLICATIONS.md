# Getting credentials — checklist and application drafts

Fill the [BRACKETS] with TRUE information about your own site/channel. Never claim traffic, audience or sales you
don't have; programs verify and will ban you. Do not paste keys into chat or commit them — put them in `.env`.

## Before you apply (all programs)
- [ ] A real public property you control: a website/blog, an Instagram/YouTube/Telegram channel, or a Slack/WhatsApp
      community with an invite page. A single-page site describing the project is fine to start.
- [ ] PAN, bank account, and a working phone/email (for payouts and verification).
- [ ] Read each program's operating agreement. Using API data for a private alert tool is usually fine; republishing
      prices publicly often is not.

## Site/channel description (adapt)
"[SITE NAME] is a [price-alert / deals] [website / Telegram channel / newsletter] for Indian shoppers. We track
publicly listed prices of electronics, appliances and fashion and notify subscribers when a genuinely lower price
than the product's own recent price history appears, linking to the retailer's product page. We do not use coupon
or incentivised traffic. Audience: [REAL numbers, or 'new, launching [month]']."

## Intended use of the API (adapt)
"We query product title, price and availability for items we feature, to show current prices and detect price drops,
at a low request rate (well under the documented limits), caching results. Every price shown links to the retailer."

## 1. Flipkart Affiliate (affiliate.flipkart.com)
1. Sign up/log in with your Flipkart account → add your property + the descriptions above.
2. Wait for approval (manual).
3. Dashboard → API → copy Affiliate ID and token → `.env`: `FLIPKART_AFFILIATE_ID`, `FLIPKART_AFFILIATE_TOKEN`.
4. `python -m scripts.check_credentials`

## 2. Amazon Associates India → PA-API
1. associates.amazon.in → sign up, add your property, accept the agreement.
2. Share affiliate links from your property; complete the qualifying sales Amazon currently requires.
3. Associates → Tools → Product Advertising API → request access → create credentials.
4. `.env`: `AMAZON_PAAPI_ACCESS_KEY`, `AMAZON_PAAPI_SECRET_KEY`, `AMAZON_PAAPI_PARTNER_TAG` (your tracking ID, e.g. name-21).
5. `python -m scripts.check_credentials` — "AssociateNotEligible"/403 means sales requirement not met yet.
   (Alternative for Amazon.in price history only: Keepa API, paid → `KEEPA_API_KEY`, `python -m scripts.import_keepa`.)

## 3. Myntra and others via an affiliate network
1. Sign up free at one network (vCommission, Admitad India, Cuelinks, Optimise).
2. Apply to each merchant's program (Myntra, Ajio, Croma, Nykaa, Tata CLiQ, Reliance Digital …) using the descriptions above.
3. In approved programs, find the product feed / datafeed / API and copy its URL.
4. `.env`: `FEED_MYNTRA_URL=...` (and `FEED_AJIO_URL`, `FEED_CROMA_URL` …). If column names differ, set
   `FEED_<KEY>_MAP='{"price":"sale_price","id":"sku"}'` (see .env.example).
5. `python -m scripts.check_credentials` shows how many products parsed per feed.

## After keys work
`python -m scripts.seed && python -m scripts.send_test_alert`, start the stack (README §8). Prices flow after the next
discovery run; deal alerts need ~1–2 weeks of history unless you import history (Keepa/`import_history.py`).
