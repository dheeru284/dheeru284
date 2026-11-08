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
│   └── chain.mjs             /api/chain   NSE option chain, best effort
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
