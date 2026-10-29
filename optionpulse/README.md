# OptionPulse AI

A calm, light-themed portal for NIFTY intraday strategies. It shows what each
strategy is looking at right now, paper-trades all of them under identical
rules, and puts oil, the rupee, India VIX, global markets and headlines next
to the chart.

**Paper trading only.** No broker connection, no authentication, no orders.
Nothing here is investment advice.

## Pages

| Page | What you get |
|---|---|
| **Today** (`/`) | NIFTY 5-minute chart with EMA 9/21, VWAP, RSI and today's paper trades marked; the paper desk (each strategy's state, open position, today's points and checks); cross-market tiles with sparklines; market-mood reading; scored headlines. Refreshes every 30 s. |
| **Strategies** (`/strategies`) | Each strategy in plain words: how it thinks, exact long/short/exit rules, parameters, when it shines or struggles, its live checks and its last 20 sessions. Plus the paper-desk rules and the market-mood filter. |
| **Performance** (`/performance`) | Paper results over 5/10/20/40 sessions. Filter by strategy, side and outcome; mood filter on, off or compared side by side; KPIs, cumulative points chart, comparison table and a sortable trade log. |

## Data sources

| Source | Used for | Notes |
|---|---|---|
| Yahoo Finance chart API (`OPTIONPULSE_PROVIDER=yahoo`, the default) | NIFTY 50 (`^NSEI`), NIFTYBEES volume, Brent, WTI, USD/INR, India VIX, gold, S&P 500 futures, US 10Y | Real prices, **delayed and unofficial**; keyless, for personal use. NIFTY has no volume, so VWAP is weighted by NIFTYBEES ETF volume (labelled in the UI). 5-minute history covers about 60 days. |
| Google News RSS, Economic Times RSS | Headlines | Scored with a transparent keyword lexicon (rising oil/VIX/yields/dollar counts as negative for NIFTY). Shown for context, **not used in trades** (no archive to test it against). |
| Deterministic mock (`OPTIONPULSE_PROVIDER=mock`) | Everything except news | Works offline. Labelled SIMULATED everywhere. |

The Angel One SmartAPI provider is planned in `docs/PHASE3_ANGEL_ONE_SMARTAPI.md`.

## Strategies

| Strategy | Style | Long when | Exit |
|---|---|---|---|
| Trend Pulse | Trend | EMA9 > EMA21, close > VWAP and EMA9, RSI 55–70 | stop 1 ATR, target 2 ATR |
| Opening Range Breakout | Breakout | first close above the 09:15–09:30 high, above VWAP, before 13:00 | stop at range low (≤ 1.5 ATR), target 2R, one trade per side per day |
| VWAP Snap-back | Mean reversion | ≥ 1.5 ATR below VWAP, RSI ≤ 30, green candle, 09:45–14:30 | target VWAP, stop 1 ATR |

Shorts mirror each rule. The full text lives in `backend/src/optionpulse/strategies.py`
and is served by `GET /api/portal/catalog`.

## How paper trades are simulated

1. A setup is read when its candle closes; the trade enters at the **next** candle's open (no look-ahead).
2. Entries 09:20–14:30, one position per strategy, 3-candle cooldown after an exit.
3. Stop and target fixed at entry; a gap fills at the open; if a candle touches both, the stop counts first.
4. Squared off at 15:20. 0.5 point slippage on entry and exit. Results are NIFTY index points (option premiums are not simulated).
5. Sessions whose data fails validation (gaps, bad candles) are not traded.
6. **Market-mood filter:** RISK_OFF (Brent ≥ +1.5%, India VIX ≥ +5% or USD/INR ≥ +0.3% since yesterday) blocks longs; RISK_ON (the mirror moves) blocks shorts. The live desk trades with it on; Performance shows both.

Trades are recomputed from market data on every request, so history and
today's live trades always follow the same rules and nothing is stored.

## Run locally

Prerequisites: Python 3.11+, Node.js 20+, and internet access for live data.

```bash
# Terminal 1: backend
cd optionpulse/backend
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest                               # 122 tests, all offline
uvicorn optionpulse.main:app --port 8000
# offline / no Yahoo access:  OPTIONPULSE_PROVIDER=mock uvicorn optionpulse.main:app --port 8000

# Terminal 2: frontend
cd optionpulse/frontend
npm install
npm run dev                          # open http://localhost:3000
```

Production build: `npm run build && npm start`. Settings are in `.env.example`.

## API (all GET, read-only)

| Route | Purpose |
|---|---|
| `/api/health` | provider, data source, `order_placement: disabled` |
| `/api/portal/overview?symbol=NIFTY&as_of=` | today: candles, live strategy states, open positions, factors, regime, news |
| `/api/portal/performance?symbol=NIFTY&sessions=20&as_of=` | per-strategy stats, equity curves and trades, mood filter on and off |
| `/api/portal/catalog` | strategy descriptions, engine rules, regime thresholds, factor notes |
| `/api/dashboard`, `/api/candles`, `/api/instruments` | the Phase 1–2 endpoints |

`as_of` (ISO 8601, naive = IST) replays any moment. Interactive docs at http://127.0.0.1:8000/docs.

## Layout

```
backend/src/optionpulse/
  schemas.py, session.py, validation.py   canonical models, NSE calendar, data checks
  indicators.py                           EMA, Wilder RSI, session VWAP, ATR
  strategy.py, strategies.py              rule sets and their documentation
  engine.py                               paper-trading engine and statistics
  macro.py, news.py                       cross-market factors, regime, headlines
  providers/  mock.py, yahoo.py           market-data sources
  portal.py, api.py                       assembly and HTTP API
frontend/  app/ (Today, Strategies, Performance)  components/  lib/
```

## Known limits

* Yahoo's feed is unofficial: it can be delayed, rate-limited or change without notice. A null bar becomes a gap and that session is not traded.
* No NSE holiday calendar yet: every weekday is a session.
* A few weeks of paper results say little about the future.
