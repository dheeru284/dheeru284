# What moves NIFTY, and what that means for weekly options

Data through 6 Nov 2026. Sources: Yahoo Finance daily history (NIFTY and India VIX from
2008; 22 global series from 2005), RBI repo decisions 2008 to Oct 2026. Every number below
is produced by `analyze.py` and can be regenerated.

## 1. Overnight drivers of NIFTY's open (2011–2026, 3,733 sessions)

| Factor (change since the last Indian session) | Correlation with gap | Last 2 years |
|---|---|---|
| S&P 500 | 0.52 | 0.45 |
| Dow / Nasdaq | 0.51 / 0.50 | 0.49 / 0.39 |
| US VIX | −0.43 | −0.47 |
| DAX / FTSE | 0.33 / 0.32 | 0.29 / 0.33 |
| Bitcoin | 0.20 | 0.35 |
| USD/INR (rupee weaker = up) | −0.16 | −0.17 |
| Brent crude | 0.03 | **−0.29** |
| US 10Y yield | 0.04 | **−0.13** |
| Gold | 0.08 | 0.20 |

- **Gap model** (OLS on 9 factors, trained 2011–19): out-of-sample 2020–26 R² 0.26. Gap
  direction is right 72% of the time, and 89% on its strongest 20% of signals.
- **Gaps fade.** After gaps of more than 1%, NIFTY moved against the gap intraday on
  average (−0.15% after gap-ups, +0.16% after gap-downs). Intraday correlations with all
  overnight factors are about zero, so the news is priced in at 9:15.

## 2. Macro regimes → NIFTY's next 21 sessions

- **US 10Y yield up more than 40 bp in 20 sessions:** NIFTY averaged −1.28% over the next
  21 sessions and was up only 39% of the time. This is the strongest bearish macro signal.
- **DXY falling more than 1%:** +1.3–1.5% next month. **DXY rising 1–3%:** +0.37%.
- **Brent crashing more than 15%:** −0.88% (demand-scare episodes such as 2008, 2015 and 2020).
- **RBI cycle:** NIFTY returned 1.7%/yr during hiking phases, versus 15.4% on hold and 13.0%
  while cutting. **The RBI began hiking on 7 Oct 2026 (repo 5.50%).**
- **Trend:** above the 200 DMA, the next month averaged +0.77% (up 59% of the time) with low
  volatility. Below it, returns were higher (+2.2%) but with 1.5× the volatility. Mean
  reversion dominates in India.

## 3. India VIX and events

- In every VIX bucket, NIFTY stayed inside the VIX-implied 1-week 1σ range 72–77% of the
  time, against the 68% a normal distribution predicts. VIX overstates realised movement.
  That gap is the volatility risk premium, which is the option seller's edge.
- Budget days move 1.31% on average, RBI days 1.02% and normal days 0.83%. But event moves
  were *smaller* than VIX implied (median 0.82–0.87×), and VIX fell afterwards. Buying a
  straddle the day before an event lost money 78% of the time.

## 4. Weekly option backtest (per lot of 65, at NIFTY 25,000)

Premiums are Black-Scholes on India VIX × 0.95 with a put skew, because no free historical
NIFTY option-chain data exists. Costs include slippage, STT, exchange fees, GST, stamp duty
and brokerage.

| Strategy | Weeks | Win % | Avg ₹/week | Worst week | Max drawdown |
|---|---|---|---|---|---|
| Iron condor 1σ/1.75σ, every week | 827 | 79 | 1,154 | −58,276 | −1,07,502 |
| **Iron condor + event, VIX and macro guard** | 477 | 80 | **1,071** | **−24,382** | **−51,826** |
| Wide condor 1.25σ/2σ + guard | 477 | 88 | 819 | −26,145 | −42,537 |
| Naked strangle 1σ | 827 | 82 | 1,797 | **−1,84,782** | −3,60,544 |
| Long ATM straddle (buying) | 827 | 35 | **−3,443** | −88,968 | −29,44,303 |

The guarded condor held up out of sample: ₹1,076/week in 2011–18 and ₹1,067 in 2019–26.

**Fragility:** if real weekly IV is 0.85 × VIX instead of 0.95 ×, the average falls to ₹160
(profit factor 1.07). With 3 pts slippage per leg it falls to ₹486. The edge is real but
thin, and it depends on getting fair fills.

## 5. Hidden and new trends (1-year rolling correlation vs its 10-year history)

1. **Crude oil has turned into NIFTY's enemy.** Correlation is −0.35, the lowest in 10 years
   (10-year average +0.03, z = −3.2). With Brent near $98, oil is the main macro risk.
2. **US yields matter again.** Correlation is −0.26, also a 10-year low (z = −2.5).
3. **Gold and NIFTY are rising together** (+0.27, a 10-year high): a liquidity / weak-dollar regime.
4. **Decoupling from Wall Street.** The 3-month correlation with the S&P 500 is −0.16, versus
   +0.28 normally.
5. **The option-seller edge is the thinnest on record.** In 2026 VIX averaged only 0.7 vol
   points above realised volatility (10-year norm about 2.6), and VIX exceeded realised vol on
   only 59% of days. Crowded weekly selling has compressed premiums.
6. **The overnight drift has disappeared.** From 2011 to 2024 NIFTY earned about 33%/yr
   overnight and lost about 15%/yr intraday. In 2025 overnight gains were 9%, and in 2026 −0.1%.
7. **Tuesday expiry (since Sep 2025)** cut average daily ranges from about 1.16% to about 0.94%.

## What was not tested

- **News sentiment:** there is no free historical news archive. The app shows live headlines as context only.
- **FII/DII daily flows:** the NSE archive was not reachable from the research machine.
- **Intraday stop-losses:** the backtest uses daily bars only.
- **Fed funds rate:** FRED timed out, so the 3-month T-bill is used as the proxy.
