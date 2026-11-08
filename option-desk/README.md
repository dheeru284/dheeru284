# NIFTY Option Desk

A daily NIFTY options desk that runs free on Netlify. It combines a 15-year backtest of
how global macro factors move Indian markets with live overnight data, so every morning
you get:

- **Trade gate**: green / amber / red for selling weekly premium, built only from rules
  that held up in the 2011–2026 backtest (event weeks, India VIX level and spikes, US VIX,
  rupee, US yields, crude, and a live check of whether options are priced rich).
- **Opening-gap model**: predicts NIFTY's gap from overnight moves in US stocks, US VIX,
  DXY, USD/INR, crude, gold, US 10Y and DAX. Out-of-sample (2020–2026) it calls the gap
  direction right 72% of the time, and 89% on its strongest signals.
- **This week's plan**: iron condor or credit-spread strikes from India VIX, model premiums,
  max loss including Indian charges, breakevens, probability of profit and lot sizing.
- **Option chain reader**: PCR, max pain, OI walls, fresh writing, ATM straddle and skew,
  from NSE (when it allows cloud requests) or the NSE / broker CSV.
- **Strategy lab**: any multi-leg payoff, Greeks and probability of profit.
- **Backtest, Macro & trends, News, Journal** tabs: full research results, hidden-trend
  detection, a headline feed tagged by factor, and a forward-test journal.

**This is a research tool, not investment advice.** SEBI found about 91% of individual F&O
traders lost money in FY25. Read the *Risk & method* tab before trading real money.

## Trade card and live exit alerts

Each weekly plan comes with a trade card:

- **Entry:** sell the basket near the close 4 sessions before expiry, only if the real net
  credit is at least the minimum shown (the model credit at IV = 0.90 × India VIX).
- **Target:** hold to expiry. Early profit-taking at 50 / 65 / 80% of the credit lowered
  returns in every test.
- **Stop-loss:** exit when the loss equals the credit (buy-back cost = 2× credit) at the
  close. This was chosen on 2011–18 and confirmed on 2019–26. As an untested safety rule,
  exit immediately if the loss reaches 1.5× the stop.

Press **“I took this trade”** to hand the position to the server-side monitor
(`netlify/functions/monitor.mjs`, every 2 minutes). It pushes alerts to your phone for:

| Alert | When |
|---|---|
| EXIT | stop met at the close, a short strike breached into the close, or loss ≥ 1.5× stop at any time |
| WARN | stop touched intraday, NIFTY ≥ 70% of the way to a short strike, a ±1.2% day, a 0.6% move in 15 min, India VIX +10% |
| WARN / INFO | high-impact headline (war, RBI, Fed, tariffs, crashes …); WARN when NIFTY or VIX is reacting in the same 15 minutes |
| TARGET | expiry afternoon with the position in profit |

Push channels (Netlify environment variables): `NTFY_TOPIC` (free ntfy app) and/or
`TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`. `ALERT_KEY` protects the position and alert
endpoints; enter it once in the app. State is kept in Netlify Blobs.

## Layout

```
option-desk/
├── site/                     static app (published)
│   ├── index.html, app.js, lib.js, styles.css
│   ├── results.json          research output the app reads
│   └── vendor/chart-4.4.1.umd.js
├── netlify/functions/        serverless data proxies (free tier)
│   ├── market.mjs            /api/market  Yahoo Finance, 1 year daily, 20 series
│   ├── news.mjs              /api/news    ET, Moneycontrol, Mint, BS, Google News RSS
│   ├── chain.mjs             /api/chain   NSE option chain, best effort
│   ├── position.mjs          /api/position  position being monitored
│   ├── alerts.mjs            /api/alerts    alert log, test push, run check now
│   └── monitor.mjs           scheduled every 2 min: exit / news / shock checks
├── netlify/lib/              shared: pricing, news scoring, storage, push, monitor
├── research/
│   ├── fetch_data.py         download history (Yahoo + FRED)
│   ├── analyze.py            factor study, gap model, regimes, events, option backtest, trends
│   └── REPORT.md             findings
└── netlify.toml
```

## Refresh the research

Live prices and news update on every page load. The backtest numbers come from
`results.json`; rebuild it every few weeks:

```bash
cd option-desk/research && python3 fetch_data.py && python3 analyze.py && cp results.json ../site/
```

Needs Python 3 with pandas and numpy. Then redeploy.

## Deploy to Netlify (free)

With the Netlify CLI and a personal access token:

```bash
cd option-desk && npx netlify-cli deploy --prod --dir site --functions netlify/functions
```

Or connect the GitHub repo in the Netlify UI: set the base directory to `option-desk`.
`netlify.toml` already sets the publish and functions folders. There is no build command.

## Daily routine

1. **8:30–9:10 IST**: open *Today*. Read the gap model and the gate. Skim *News*.
2. **Entry day** (4 sessions before the Tuesday expiry, usually Wednesday): if the gate is
   green, paste the live ATM straddle so the gate can check that options are priced rich.
   Use real bid/ask, not the model premiums.
3. Risk 1–2% of capital per trade. Exit on a close beyond a short strike or a loss of 2× the credit.
4. Log every plan, including stand-aside weeks, in *Journal*, and settle it at expiry.
   Paper-trade 12–20 weeks before committing real money.
