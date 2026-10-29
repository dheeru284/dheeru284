# OptionPulse AI

Five-minute NIFTY setup dashboard. **Phases 1–2: simulated data only.** No
authentication, no broker connection, no order placement.

```
optionpulse/
├── backend/          FastAPI + pure-Python domain (Python ≥ 3.11)
│   ├── src/optionpulse/
│   │   ├── schemas.py      canonical Instrument / Candle / CandleSeries
│   │   ├── session.py      NSE session calendar (09:15–15:30 IST)
│   │   ├── validation.py   gap / order / alignment / integrity / staleness checks
│   │   ├── indicators.py   EMA, Wilder RSI, session VWAP
│   │   ├── strategy.py     LONG_SETUP / SHORT_SETUP / NO_TRADE / DATA_INVALID
│   │   ├── providers/      MarketDataProvider contract + deterministic mock
│   │   └── api.py          read-only HTTP API (GET only)
│   └── tests/              pytest suite
├── frontend/         Next.js 15 (App Router) dashboard
└── docs/PHASE3_ANGEL_ONE_SMARTAPI.md
```

## Run locally

Prerequisites: Python 3.11+, Node.js 20+.

```bash
# 1. Backend (terminal 1)
cd optionpulse/backend
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest                               # 72 tests
uvicorn optionpulse.main:app --reload --port 8000

# 2. Frontend (terminal 2)
cd optionpulse/frontend
npm install
npm run dev                          # http://localhost:3000
```

The frontend proxies `/api/*` to `OPTIONPULSE_BACKEND_URL`
(default `http://127.0.0.1:8000`). Production build: `npm run build && npm start`.
Type check: `npm run typecheck`. Settings are listed in `.env.example`.

## API

| Route | Purpose |
|---|---|
| `GET /api/health` | provider, data source, `order_placement: disabled` |
| `GET /api/instruments` | canonical instruments |
| `GET /api/candles?symbol=NIFTY&interval=FIVE_MINUTE&sessions=1&as_of=` | raw `CandleSeries` |
| `GET /api/dashboard?symbol=NIFTY&as_of=` | session candles + indicators + strategy result |

`as_of` (ISO 8601; naive values are read as IST) replays any moment. Only
candles that have closed by `as_of` are returned. Interactive docs:
http://127.0.0.1:8000/docs.

## Simulated data

`MockMarketDataProvider` generates one-minute bars per trading day from
`(seed, symbol, date)` with its own SplitMix64 PRNG and SHA-256 seeding, then
aggregates to 3/5/15 minutes. Each day gets a trend-up, trend-down or range
regime and U-shaped intraday volume. The same request always returns the same
candles; a golden-hash test pins the output. Every series carries
`source: SIMULATED`, and the UI shows it in a banner, badge and chart
watermark. The volume is invented: the real NIFTY 50 index has none (see
Phase 3 plan, item 5).

## Strategy rules

Evaluated on the last **closed** five-minute candle, with three previous
sessions loaded so indicators are warm at 09:15.

| Signal | Conditions |
|---|---|
| `LONG_SETUP` | EMA9 > EMA21, close > VWAP, close > EMA9, 55 ≤ RSI14 ≤ 70 |
| `SHORT_SETUP` | EMA9 < EMA21, close < VWAP, close < EMA9, 30 ≤ RSI14 ≤ 45 |
| `NO_TRADE` | data valid, neither side passes every check |
| `DATA_INVALID` | validation issue (empty, gap, duplicate, out of order, misaligned, bad OHLC, future or stale candle), fewer than 30 candles, or zero volume (no VWAP) |

Indicator definitions: EMA seeded with the SMA of the first *n* closes,
α = 2/(n+1); RSI uses Wilder smoothing (checked against the StockCharts
example); VWAP uses typical price (H+L+C)/3, reset at each session open.
Thresholds live in `StrategyConfig`.

A setup describes the chart against fixed rules. It is not advice.

## Known limits

* No NSE holiday calendar yet: every weekday is a session.
* Mock supports 1, 3, 5 and 15-minute intervals (they divide the 375-minute session).
