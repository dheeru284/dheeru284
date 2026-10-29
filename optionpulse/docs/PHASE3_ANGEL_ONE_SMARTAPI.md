# Phase 3 plan: Angel One SmartAPI, read-only

Goal: replace `MockMarketDataProvider` with an `AngelOneProvider` that returns
the same canonical `CandleSeries` (`source = BROKER_HISTORICAL`), with **no
order capability of any kind**. The dashboard, indicators and strategy must
not change.

## What this is based on

* **Official SDK source**, `smartapi-python` 1.5.5 from PyPI
  (`github.com/angel-one/smartapi-python`), read line by line on 2026-10-29.
  Everything marked *(SDK)* below is quoted from that code.
* **Official docs** (`smartapi.angelone.in/docs`) were **not reachable** from
  the build environment (DNS blocked by its network policy). Items marked
  *(verify in docs)* come from prior knowledge and must be checked against the
  docs before implementation.

## Facts from the SDK source

| Item | Value *(SDK)* |
|---|---|
| REST root | `https://apiconnect.angelone.in` |
| Login | `POST /rest/auth/angelbroking/user/v1/loginByPassword` body `{clientcode, password (PIN), totp}` → `data.jwtToken`, `data.refreshToken`, `data.feedToken` |
| Refresh | `POST /rest/auth/angelbroking/jwt/v1/generateTokens` body `{refreshToken}` |
| Profile | `GET /rest/secure/angelbroking/user/v1/getProfile` |
| Logout | `POST /rest/secure/angelbroking/user/v1/logout` body `{clientcode}` |
| Candles | `POST /rest/secure/angelbroking/historical/v1/getCandleData` body `{exchange, symboltoken, interval, fromdate, todate}`; README example dates `"2021-02-08 09:00"` |
| LTP | `POST /rest/secure/angelbroking/order/v1/getLtpData` body `{exchange, tradingsymbol, symboltoken}` |
| Quote | `POST /rest/secure/angelbroking/market/v1/quote` body `{mode, exchangeTokens}` |
| Scrip search | `POST /rest/secure/angelbroking/order/v1/searchScrip` body `{exchange, searchscrip}` |
| Headers | `Content-type`, `Accept: application/json`, `X-UserType: USER`, `X-SourceID: WEB`, `X-ClientLocalIP`, `X-ClientPublicIP`, `X-MACAddress`, `X-PrivateKey: <api_key>`, `Authorization: Bearer <jwt>` |
| Errors | JSON `error_type` maps to exceptions; HTTP 403 + `TokenException` = session expired |
| Timeout | 7 s default |
| WebSocket V2 | `wss://smartapisocket.angelone.in/smart-stream`; modes 1 LTP, 2 QUOTE, 3 SNAP_QUOTE, 4 DEPTH; exchangeType 1 NSE_CM, 2 NSE_FO; DEPTH capped at 50 tokens |
| Interval names | the SDK passes them through; `Interval` in `schemas.py` already uses Angel's names (`FIVE_MINUTE`, …) |

## Problems found in the SDK

1. **Secrets written to disk.** Constructing `SmartConnect` creates
   `./logs/<date>/app.log`. Any response with `status: false` logs the full
   request headers (`X-PrivateKey` = API key) and the request params, which
   for login are the client code, **PIN and TOTP**. Exceptions log the
   headers including the `Authorization` bearer token.
2. **Network call at import.** The class body calls `api.ipify.org`, then a
   `finally` block overwrites the result with the hard-coded public IP
   `106.193.147.98`, which is sent on every request.
3. **TLS verification off on the feed.** `SmartWebSocketV2` runs with
   `sslopt={"cert_reqs": ssl.CERT_NONE}`; the REST client also calls
   `urllib3.disable_warnings()` globally.
4. **Undeclared dependencies.** Imports `logzero`, `websocket-client`
   (and the README needs `pyotp`, `pycryptodome`), but the wheel metadata
   only declares `requests`, `six`, `python-dateutil`.
5. **Order methods on the same object.** `placeOrder`, `modifyOrder`,
   `cancelOrder`, `gttCreateRule`, `convertPosition` sit on the same
   `SmartConnect` instance as `getCandleData`, so holding a client means
   holding order capability.

## Decision: thin in-house read-only client, SDK as the reference

Do not import `SmartApi` at runtime. Implement `optionpulse/providers/angelone/`
with `httpx`, mirroring the SDK's routes and headers exactly, exposing only:

```
login(), refresh(), logout(), profile()
candles(exchange, token, interval, from, to)
ltp(exchange, tradingsymbol, token)
search_scrip(exchange, query)
```

Order routes are never defined, so nothing can call them. A unit test
asserts the client's route table contains no `order/v1/placeOrder`,
`modifyOrder`, `cancelOrder`, `convertPosition` or `gtt` paths
(`getLtpData` and `searchScrip` live under `order/v1/` but are reads; allow
them by exact path). If the user prefers the SDK itself, wrap it in an
adapter that: sets `logzero` to a null handler before
construction, runs from a temp CWD, patches `clientPublicIp`/`clientLocalIp`
to real values, and is exposed only through the same 7-method interface.

## Work items

1. **Secrets and config.** `OPTIONPULSE_PROVIDER=angelone`; read
   `ANGEL_API_KEY`, `ANGEL_CLIENT_CODE`, `ANGEL_PIN`, `ANGEL_TOTP_SECRET`
   from the environment / a git-ignored `.env`. Generate TOTP with `pyotp`.
   Never log request bodies or headers; redact in exception messages. Keep
   tokens in memory only.
2. **Session manager.** Login at startup, refresh on 403 `TokenException`
   once, then fail closed (`DATA_INVALID`, provider status `AUTH_ERROR`).
   Single-flight refresh. Logout on shutdown. *(verify in docs: JWT lifetime
   and whether sessions end daily around midnight.)*
3. **Instrument master.** Download Angel's scrip master JSON once a day,
   cache to disk, resolve `broker_token` for `NIFTY` (index) and the
   current-month `NIFTY` future. *(verify in docs: master URL, and that
   NIFTY 50 spot is `NSE` token `99926000`.)*
4. **Candle adapter.** Map each row to `Candle`; parse the timestamp with
   its `+05:30` offset; drop the in-progress bar (end > now); chunk long
   ranges by the per-interval day limit; translate errors to provider
   exceptions. *(verify in docs: row order `[timestamp, open, high, low,
   close, volume]`, per-interval maximum days per request, and rate limits
   per second/minute; add a token-bucket limiter to match.)*
5. **VWAP needs a volume source.** Angel returns zero volume for the NIFTY
   spot index, so `evaluate` will return `DATA_INVALID / VWAP_UNAVAILABLE`
   (already tested). Plan: chart the index, compute VWAP and the strategy's
   VWAP check on the current-month NIFTY future (`NFO`), rolling on expiry.
   This needs a small `StrategyInput` change: price series + volume series.
   Decide whether the strategy should evaluate the future end-to-end instead
   (simpler, one series) and only display the index.
6. **Holidays.** Load NSE's trading-holiday list so validation does not flag
   holidays as missing sessions and `latest_session_day` skips them.
7. **UI labelling.** The banner switches on `source`: `SIMULATED` (amber,
   as now) vs `BROKER_HISTORICAL` ("Delayed / historical, read-only").
   Show provider health and last successful fetch time; on any provider
   error show `DATA_INVALID`, never stale numbers silently.
8. **Tests.** Recorded JSON fixtures for login, candles, errors and token
   expiry; `httpx.MockTransport` so CI makes no network calls; contract test
   that `AngelOneProvider` and `MockMarketDataProvider` produce series that
   pass `validate_series`; the no-order-routes test; a log-capture test
   proving the PIN, TOTP, API key and JWT never appear in logs.
9. **Manual smoke test** (needs the user's credentials, run locally only):
   fetch one day of 5-minute NIFTY futures candles and compare five bars to
   the Angel One app chart.

## Questions for the user before starting

* Which SmartAPI app type will the key be created under? Prefer a
  market-data / historical-data key over a trading key if Angel offers one
  for your account *(verify in docs)*.
* VWAP source: NIFTY current-month future (recommended), or evaluate the
  strategy entirely on the future?
* Is polling historical candles every 15–30 s enough for Phase 3, deferring
  the WebSocket feed (which also needs the TLS issue above handled)?

## Out of scope for Phase 3

Order placement, modification, cancellation, GTT, positions, holdings, funds,
and any WebSocket order-update stream.
