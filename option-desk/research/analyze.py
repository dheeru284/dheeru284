"""Option Desk research engine.

What it does, on real daily history (Yahoo Finance; see fetch_data.py):
  1. Factor study  – how overnight moves in US stocks, US VIX, DXY, USD/INR, crude,
                     gold, US yields, Asia predict NIFTY's gap, day and next week.
  2. Gap model     – OLS fitted 2011-2019, scored out-of-sample 2020-today.
  3. Regimes       – VIX buckets, trend, RBI/Fed rate cycles, crude/INR/yield shocks.
  4. Events        – RBI decisions, Union Budgets, election results: move vs implied.
  5. Option backtest – weekly NIFTY option strategies priced with Black-Scholes off
                     India VIX (no free historical option-chain data exists), with
                     skew, slippage, STT, exchange charges, GST and brokerage.
  6. Trends        – correlation regime shifts, overnight-vs-intraday drift,
                     volatility risk premium by year, expiry-day effects.
Writes results.json (consumed by the web app) and REPORT.md.
"""
import json, math, os
from datetime import date
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "data")
LOT = 65
SCALE_SPOT = 25000.0          # P&L is restated "at today's index level"
SQ = math.sqrt


def load(name, col="close"):
    df = pd.read_csv(os.path.join(D, f"{name}.csv"), parse_dates=["date"]).set_index("date")
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df if col is None else df[col].astype(float)


# ----------------------------------------------------------------------------- data
nifty = load("NIFTY", None)
nifty = nifty[nifty.close > 0]
vix = load("INDIAVIX")
idx = nifty.index[nifty.index >= "2008-03-03"]
P = pd.DataFrame(index=idx)
P["close"] = nifty.close.reindex(idx)
P["open"] = nifty.open.reindex(idx)
P["high"] = nifty.high.reindex(idx)
P["low"] = nifty.low.reindex(idx)
P["vix"] = vix.reindex(idx).ffill()
P["bank"] = load("BANKNIFTY").reindex(idx).ffill()
P["pc"] = P.close.shift()
P["cc"] = P.close / P.pc - 1
P["gap"] = P.open / P.pc - 1
P["oc"] = P.close / P.open - 1
P.loc[P.index < "2011-01-01", ["gap", "oc"]] = np.nan   # bad opens in Yahoo pre-2011
P.loc[(P.gap.abs() < 2e-4), ["gap", "oc"]] = np.nan       # open==prev close → stale open
P["fwd1"] = P.cc.shift(-1)
P["fwd5"] = P.close.shift(-5) / P.close - 1
P["fwd21"] = P.close.shift(-21) / P.close - 1
P["dma50"] = P.close.rolling(50).mean()
P["dma200"] = P.close.rolling(200).mean()

OVERNIGHT = {  # factor: (file, kind)  kind: pct change, or bps for yields
    "S&P 500": ("SP500", "pct"), "Nasdaq": ("NASDAQ", "pct"), "Dow": ("DOW", "pct"),
    "US VIX": ("USVIX", "pct"), "Dollar index (DXY)": ("DXY", "pct"),
    "USD/INR": ("USDINR", "pct"), "Brent crude": ("BRENT", "pct"), "WTI crude": ("WTI", "pct"),
    "Gold": ("GOLD", "pct"), "Silver": ("SILVER", "pct"), "Copper": ("COPPER", "pct"),
    "Natural gas": ("NATGAS", "pct"), "US 10Y yield": ("US10Y", "bps"),
    "US 30Y yield": ("US30Y", "bps"), "US 3M T-bill": ("US13W", "bps"),
    "FTSE 100": ("FTSE", "pct"), "DAX": ("DAX", "pct"), "Bitcoin": ("BITCOIN", "pct"),
}
CONCURRENT = {"Nikkei": "NIKKEI", "Hang Seng": "HANGSENG", "Shanghai": "SHANGHAI"}

raw = {}
for k, (f, kind) in OVERNIGHT.items():
    s = load(f).dropna()
    s = s[s > 0]
    raw[k] = (s, kind)
    # value known before the Indian open on day t = last print dated strictly before t
    asof = s.reindex(s.index.union(idx)).ffill().shift(1).reindex(idx)
    # The shift(1) on the union index picks the last value dated < t.
    if kind == "pct":
        P["x_" + k] = asof / asof.shift(1) - 1
    else:
        P["x_" + k] = (asof - asof.shift(1)) * (10 if f in ("US10Y", "US30Y", "US13W") else 1)  # ^TNX is in %, ×100 bps / 10? see below
    P["lvl_" + k] = asof
# ^TNX/^TYX/^IRX quote yield in percent (e.g. 4.25) → bps change = diff × 100
for k in ("US 10Y yield", "US 30Y yield", "US 3M T-bill"):
    P["x_" + k] = P["lvl_" + k].diff() * 100
for k, f in CONCURRENT.items():
    s = load(f).dropna()
    P["c_" + k] = s.reindex(idx).pct_change(fill_method=None)

FACTORS = list(OVERNIGHT)


def corr(a, b):
    m = a.notna() & b.notna()
    if m.sum() < 60:
        return np.nan, 0
    return float(np.corrcoef(a[m], b[m])[0, 1]), int(m.sum())


def tstat(r, n):
    return r * SQ(max(n - 2, 1)) / SQ(max(1 - r * r, 1e-9))


# ----------------------------------------------------------------------------- 1. factors
def factor_table(df):
    rows = []
    for k in FACTORS:
        x = df["x_" + k]
        rg, n = corr(x, df.gap)
        rc, _ = corr(x, df.cc)
        ro, _ = corr(x, df.oc)
        # big-move hit rate: when factor in its top/bottom decile, how often does NIFTY gap the same way
        q = x.quantile([0.1, 0.9])
        big = df[(x <= q.iloc[0]) | (x >= q.iloc[1])]
        hit = np.nan
        if len(big) > 30:
            s = np.sign(big["x_" + k]) * np.sign(big.gap)
            hit = float((s > 0).sum() / s.ne(0).sum()) if s.ne(0).sum() else np.nan
        # NIFTY gap on factor-shock days (factor's own top/bottom decile)
        up = df[x >= q.iloc[1]].gap.mean() * 100
        dn = df[x <= q.iloc[0]].gap.mean() * 100
        rows.append(dict(factor=k, corr_gap=rg, corr_day=rc, corr_intraday=ro, n=n,
                         t_gap=tstat(rg, n) if n else np.nan, big_move_hit=hit,
                         gap_when_factor_top10=up, gap_when_factor_bottom10=dn))
    return pd.DataFrame(rows).sort_values("corr_gap", key=lambda s: -s.abs())


G = P[P.gap.notna()]
fac_all = factor_table(G)
fac_recent = factor_table(G[G.index >= G.index[-1] - pd.Timedelta(days=730)])
conc = {k: corr(P["c_" + k], P.cc)[0] for k in CONCURRENT}

# ----------------------------------------------------------------------------- 2. gap model
MODEL_X = ["S&P 500", "Nasdaq", "US VIX", "Dollar index (DXY)", "USD/INR", "Brent crude",
           "Gold", "US 10Y yield", "DAX"]


def ols(X, y):
    X1 = np.column_stack([np.ones(len(X)), X])
    b, *_ = np.linalg.lstsq(X1, y, rcond=None)
    return b


cols = ["x_" + k for k in MODEL_X]
M = G[cols + ["gap", "oc", "cc"]].dropna()
# winsorise factors at 1/99 pct so 2020 crash prints don't dominate
lo, hi = M[cols].quantile(0.01), M[cols].quantile(0.99)
Mw = M.copy(); Mw[cols] = Mw[cols].clip(lo, hi, axis=1)
train, test = Mw[Mw.index < "2020-01-01"], Mw[Mw.index >= "2020-01-01"]
beta = ols(train[cols].values, train.gap.values)
pred = beta[0] + test[cols].values @ beta[1:]
res = test.gap.values - pred
r2_oos = 1 - (res ** 2).sum() / ((test.gap.values - test.gap.mean()) ** 2).sum()
dir_hit = float((np.sign(pred) == np.sign(test.gap.values)).mean())
big_pred = np.abs(pred) > np.quantile(np.abs(pred), 0.8)
dir_hit_big = float((np.sign(pred[big_pred]) == np.sign(test.gap.values[big_pred])).mean())
beta_full = ols(Mw[cols].values, Mw.gap.values)   # shipped to the app
gap_model = dict(
    factors=MODEL_X, intercept=float(beta_full[0]),
    coef={k: float(c) for k, c in zip(MODEL_X, beta_full[1:])},
    clip_lo={k: float(lo["x_" + k]) for k in MODEL_X}, clip_hi={k: float(hi["x_" + k]) for k in MODEL_X},
    oos_r2=float(r2_oos), oos_direction_hit=dir_hit, oos_direction_hit_top20=dir_hit_big,
    oos_period=f"{test.index[0].date()} → {test.index[-1].date()}", n_test=int(len(test)),
    units="factor % change as fraction (bps for yields); output is NIFTY gap as fraction")
# does the gap continue or fade intraday?
gap_follow = {}
for name, cond in {"gap up > 0.5%": G.gap > 0.005, "gap down < -0.5%": G.gap < -0.005,
                   "gap up > 1%": G.gap > 0.01, "gap down < -1%": G.gap < -0.01}.items():
    sub = G[cond]
    gap_follow[name] = dict(n=int(len(sub)), avg_gap=float(sub.gap.mean() * 100),
                            avg_intraday=float(sub.oc.mean() * 100),
                            pct_continue=float((np.sign(sub.oc) == np.sign(sub.gap)).mean()),
                            pct_fill=float(((sub.gap > 0) & (sub.low <= sub.pc) | (sub.gap < 0) & (sub.high >= sub.pc)).mean()))

# ----------------------------------------------------------------------------- 3. regimes
def bucket_stats(series, bins, labels, target="fwd5"):
    out = []
    b = pd.cut(series, bins=bins, labels=labels)
    for lab in labels:
        sub = P[b == lab]
        if len(sub) < 20:
            continue
        out.append(dict(bucket=lab, days=int(len(sub)), mean_fwd5=float(sub.fwd5.mean() * 100),
                        mean_fwd21=float(sub.fwd21.mean() * 100), up_pct_fwd21=float((sub.fwd21 > 0).mean()),
                        daily_vol=float(sub.cc.std() * 100)))
    return out


# VIX regimes: realised 5-day move vs VIX-implied 1σ
P["impl5"] = P.vix / 100 * SQ(7 / 365)
P["inside1s"] = (P.fwd5.abs() <= P.impl5)
vix_reg = []
for lab, a, b in [("<12", 0, 12), ("12-15", 12, 15), ("15-18", 15, 18), ("18-22", 18, 22), ("22-30", 22, 30), (">30", 30, 200)]:
    sub = P[(P.vix >= a) & (P.vix < b) & P.fwd5.notna()]
    vix_reg.append(dict(bucket=lab, days=int(len(sub)), share_of_time=float(len(sub) / P.fwd5.notna().sum()),
                        implied_1s_week=float(sub.impl5.mean() * 100), realised_abs_week=float(sub.fwd5.abs().mean() * 100),
                        stayed_inside_1s=float(sub.inside1s.mean()), mean_fwd21=float(sub.fwd21.mean() * 100),
                        worst_week=float(sub.fwd5.min() * 100)))
# expected under normal: 68% inside 1σ

trend = {}
for name, cond in {"Above 200 DMA": P.close > P.dma200, "Below 200 DMA": P.close <= P.dma200,
                   "50>200 & above 50": (P.dma50 > P.dma200) & (P.close > P.dma50),
                   "50<200 & below 50": (P.dma50 < P.dma200) & (P.close < P.dma50)}.items():
    sub = P[cond & P.fwd21.notna() & P.dma200.notna()]
    trend[name] = dict(days=int(len(sub)), mean_fwd5=float(sub.fwd5.mean() * 100), mean_fwd21=float(sub.fwd21.mean() * 100),
                       up_pct_fwd21=float((sub.fwd21 > 0).mean()), daily_vol=float(sub.cc.std() * 100),
                       avg_vix=float(sub.vix.mean()))

# macro shocks: 20-day change in factor vs next-month NIFTY
def chg20(k):
    lvl = P["lvl_" + k]
    return (lvl - lvl.shift(20)) * 100 if OVERNIGHT[k][1] == "bps" else lvl / lvl.shift(20) - 1


macro = {}
for k, bins, labels in [
    ("Brent crude", [-9, -0.15, -0.05, 0.05, 0.15, 9], ["< -15%", "-15..-5%", "flat ±5%", "+5..15%", "> +15%"]),
    ("USD/INR", [-9, -0.015, -0.005, 0.005, 0.015, 9], ["INR +1.5%↑", "INR +0.5..1.5%", "flat", "INR -0.5..1.5%", "INR -1.5%↓"]),
    ("US 10Y yield", [-900, -40, -15, 15, 40, 900], ["< -40bp", "-40..-15bp", "flat", "+15..40bp", "> +40bp"]),
    ("Dollar index (DXY)", [-9, -0.03, -0.01, 0.01, 0.03, 9], ["< -3%", "-3..-1%", "flat", "+1..3%", "> +3%"]),
    ("US VIX", [-9, -0.25, -0.1, 0.1, 0.25, 9], ["< -25%", "-25..-10%", "flat", "+10..25%", "> +25%"]),
    ("Gold", [-9, -0.05, -0.02, 0.02, 0.05, 9], ["< -5%", "-5..-2%", "flat", "+2..5%", "> +5%"]),
    ("S&P 500", [-9, -0.05, -0.02, 0.02, 0.05, 9], ["< -5%", "-5..-2%", "flat", "+2..5%", "> +5%"]),
]:
    macro[k] = bucket_stats(chg20(k), bins, labels)

# Rate cycles
RBI = [  # date, repo rate after decision (changes only + latest)
    ("2008-01-01", 7.75), ("2008-06-12", 8.00), ("2008-06-25", 8.50), ("2008-07-30", 9.00),
    ("2008-10-20", 8.00), ("2008-11-03", 7.50), ("2008-12-08", 6.50), ("2009-01-05", 5.50),
    ("2009-03-05", 5.00), ("2009-04-21", 4.75), ("2010-03-19", 5.00), ("2010-04-20", 5.25),
    ("2010-07-02", 5.50), ("2010-07-27", 5.75), ("2010-09-16", 6.00), ("2010-11-02", 6.25),
    ("2011-01-25", 6.50), ("2011-03-17", 6.75), ("2011-05-03", 7.25), ("2011-06-16", 7.50),
    ("2011-07-26", 8.00), ("2011-09-16", 8.25), ("2011-10-25", 8.50), ("2012-04-17", 8.00),
    ("2013-01-29", 7.75), ("2013-03-19", 7.50), ("2013-05-03", 7.25), ("2013-09-20", 7.50),
    ("2013-10-29", 7.75), ("2014-01-28", 8.00), ("2015-01-15", 7.75), ("2015-03-04", 7.50),
    ("2015-06-02", 7.25), ("2015-09-29", 6.75), ("2016-04-05", 6.50), ("2016-10-04", 6.25),
    ("2017-08-02", 6.00), ("2018-06-06", 6.25), ("2018-08-01", 6.50), ("2019-02-07", 6.25),
    ("2019-04-04", 6.00), ("2019-06-06", 5.75), ("2019-08-07", 5.40), ("2019-10-04", 5.15),
    ("2020-03-27", 4.40), ("2020-05-22", 4.00), ("2022-05-04", 4.40), ("2022-06-08", 4.90),
    ("2022-08-05", 5.40), ("2022-09-30", 5.90), ("2022-12-07", 6.25), ("2023-02-08", 6.50),
    ("2025-02-07", 6.25), ("2025-04-09", 6.00), ("2025-06-06", 5.50), ("2025-12-05", 5.25),
    ("2026-10-07", 5.50)]
rbi = pd.Series({pd.Timestamp(d): r for d, r in RBI}).sort_index()
P["repo"] = rbi.reindex(rbi.index.union(idx)).ffill().reindex(idx)
P["repo_chg_6m"] = P.repo - P.repo.shift(126)
P["fed"] = P["lvl_US 3M T-bill"]
P["fed_chg_6m"] = (P.fed - P.fed.shift(126)) * 100
cycles = {}
for name, cond in {
    "RBI cutting (6m)": P.repo_chg_6m < 0, "RBI hiking (6m)": P.repo_chg_6m > 0, "RBI on hold (6m)": P.repo_chg_6m == 0,
    "Fed easing (T-bill −50bp/6m)": P.fed_chg_6m < -50, "Fed tightening (T-bill +50bp/6m)": P.fed_chg_6m > 50,
    "Fed steady": P.fed_chg_6m.abs() <= 50}.items():
    sub = P[cond & P.cc.notna()]
    ann = (1 + sub.cc).prod() ** (252 / max(len(sub), 1)) - 1
    cycles[name] = dict(days=int(len(sub)), ann_return=float(ann * 100), daily_vol=float(sub.cc.std() * 100),
                        avg_vix=float(sub.vix.mean()))

dow = {}
for d, name in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri"]):
    for era, cond in {"2019-08/2025": (P.index >= "2019-02-11") & (P.index < "2025-09-01"),
                      "since Sep-2025 (Tue expiry)": P.index >= "2025-09-01"}.items():
        sub = P[(P.index.dayofweek == d) & cond]
        dow.setdefault(name, {})[era] = dict(n=int(len(sub)), mean=float(sub.cc.mean() * 100),
                                             abs_move=float(sub.cc.abs().mean() * 100),
                                             range=float(((sub.high - sub.low) / sub.pc).mean() * 100))

# ----------------------------------------------------------------------------- 4. events
BUDGET = ["2009-07-06", "2010-02-26", "2011-02-28", "2012-03-16", "2013-02-28", "2014-02-17", "2014-07-10",
          "2015-02-28", "2016-02-29", "2017-02-01", "2018-02-01", "2019-02-01", "2019-07-05", "2020-02-01",
          "2021-02-01", "2022-02-01", "2023-02-01", "2024-02-01", "2024-07-23", "2025-02-01", "2026-02-01"]
ELECTION = ["2009-05-18", "2014-05-16", "2019-05-23", "2024-06-04"]
RBI_DAYS = [d for d, _ in RBI[1:]] + ["2023-04-06", "2023-06-08", "2023-08-10", "2023-10-06", "2023-12-08",
                                      "2024-02-08", "2024-04-05", "2024-06-07", "2024-08-08", "2024-10-09",
                                      "2024-12-06", "2025-08-06", "2025-10-01", "2026-02-06", "2026-04-08",
                                      "2026-06-05", "2026-08-05"]
P["daily1s"] = P.vix.shift() / 100 / SQ(365)
normal_ratio = float((P.cc.abs() / P.daily1s).median())


def event_stats(days, name):
    rows = []
    for d in sorted(set(days)):
        t = pd.Timestamp(d)
        if t not in P.index:
            nxt = P.index[P.index >= t]
            if not len(nxt) or (nxt[0] - t).days > 3:
                continue
            t = nxt[0]
        r = P.loc[t]
        i = P.index.get_loc(t)
        vix_before = P.vix.iloc[i - 1]
        rows.append(dict(date=str(t.date()), move=float(r.cc * 100), implied_1d=float(r.daily1s * 100),
                         ratio=float(abs(r.cc) / r.daily1s), vix_before=float(vix_before),
                         vix_after=float(r.vix), vix_chg=float(r.vix / vix_before - 1)))
    df = pd.DataFrame(rows)
    return dict(name=name, n=len(df), avg_abs_move=float(df.move.abs().mean()), median_ratio_to_implied=float(df.ratio.median()),
                pct_beat_implied=float((df.ratio > 1).mean()), avg_vix_change=float(df.vix_chg.mean() * 100),
                biggest=df.reindex(df.move.abs().sort_values(ascending=False).index).head(5).to_dict("records"))


events = [event_stats(BUDGET, "Union Budget"), event_stats(ELECTION, "General election result"),
          event_stats(RBI_DAYS, "RBI policy day")]
events_normal = dict(avg_abs_move=float(P.cc.abs().mean() * 100), median_ratio_to_implied=normal_ratio)


# ----------------------------------------------------------------------------- 5. option backtest
def ncdf(x):
    return 0.5 * (1 + math.erf(x / SQ(2)))


def bs(S, K, T, s, typ, r=0.065):
    if T <= 0:
        return max(0.0, S - K) if typ == "C" else max(0.0, K - S)
    d1 = (math.log(S / K) + (r + s * s / 2) * T) / (s * SQ(T)); d2 = d1 - s * SQ(T)
    if typ == "C":
        return S * ncdf(d1) - K * math.exp(-r * T) * ncdf(d2)
    return K * math.exp(-r * T) * ncdf(-d2) - S * ncdf(-d1)


def iv_at(K, S, atm, T):
    z = math.log(K / S) / (atm * SQ(T))
    return max(0.05, atm * (1 - 0.06 * z + 0.01 * z * z))   # put skew + smile


def expiries(start="2011-01-01"):
    """Weekly expiry proxy: Thursday until Aug-2025, Tuesday after (holiday → previous day)."""
    days = P.index[P.index >= start]
    out = []
    for wk, g in pd.Series(days, index=days).groupby(days.to_period("W-SUN")):
        target = 1 if g.index[0] >= pd.Timestamp("2025-09-01") else 3
        cand = g[g.index.dayofweek <= target]
        if len(cand):
            out.append(cand.index[-1])
    return out


EXP = expiries()
EVENT_SET = set(pd.Timestamp(d) for d in BUDGET + ELECTION + RBI_DAYS)


def run_strategy(name, legs_fn, flt=None, atm_mult=0.95, slip_pts=0.75, hold=4):
    """legs_fn(S, sig_T, row) -> list of (qty, type, K) with qty +1 long / -1 short.
    Enter at close `hold` sessions before expiry, settle at expiry close."""
    trades = []
    for e in EXP:
        i = P.index.get_loc(e)
        if i - hold < 200:
            continue
        t0 = P.index[i - hold]
        row = P.loc[t0]
        if np.isnan(row.vix):
            continue
        if flt is not None and not flt(row, t0, e):
            continue
        S, ST = row.close, P.close.iloc[i]
        T = max((e - t0).days, 1) / 365 + 0.25 / 365
        atm = row.vix / 100 * atm_mult
        sigT = atm * SQ(T)
        step = S * 0.002
        legs = legs_fn(S, sigT, row)
        if not legs:
            continue
        prem = 0.0; sold = 0.0; pnl = 0.0; slip = 0.0
        for q, typ, K in legs:
            K = round(K / step) * step
            p = bs(S, K, T, iv_at(K, S, atm, T), typ)
            pay = max(0.0, ST - K) if typ == "C" else max(0.0, K - ST)
            pnl += q * (pay - p)
            prem += -q * p
            if q < 0:
                sold += p
            slip += slip_pts * S / SCALE_SPOT
        # charges (in index points per unit): STT 0.15% on sold premium, exch 0.0355% +GST 18%,
        # stamp 0.003% on bought premium, brokerage ₹20/leg → per unit
        bought = sum(bs(S, round(K / step) * step, T, iv_at(round(K / step) * step, S, atm, T), typ)
                     for q, typ, K in legs if q > 0)
        charges = 0.0015 * sold + (sold + bought) * 0.000355 * 1.18 + 0.00003 * bought + 20 * len(legs) * 1.18 / LOT * S / SCALE_SPOT
        # exercise STT on ITM long legs at expiry: 0.15% of intrinsic value (from Apr-2026 rules)
        itm_long = sum(max(0.0, (ST - round(K / step) * step) if typ == "C" else (round(K / step) * step - ST))
                       for q, typ, K in legs if q > 0)
        charges += 0.0015 * itm_long
        net = pnl - slip - charges
        scale = SCALE_SPOT / S            # restate at today's NIFTY level
        widths = [abs(a[2] - b[2]) for a in legs for b in legs if a[1] == b[1] and a[0] != b[0]]
        risk = (max(widths) - prem) if widths else S * 0.1     # naked: notional 10% stress as "risk"
        trades.append(dict(entry=str(t0.date()), expiry=str(e.date()), spot=S, settle=ST, vix=float(row.vix),
                           credit=prem * scale, pnl_pts=net * scale, pnl_rs=net * scale * LOT,
                           risk_rs=risk * scale * LOT))
    df = pd.DataFrame(trades)
    return name, df


def summarise(name, df, desc):
    if df.empty:
        return dict(name=name, desc=desc, trades=0)
    eq = df.pnl_rs.cumsum()
    dd = (eq - eq.cummax()).min()
    wins = df[df.pnl_rs > 0].pnl_rs.sum(); losses = -df[df.pnl_rs < 0].pnl_rs.sum()
    df = df.assign(year=pd.to_datetime(df.entry).dt.year)
    yearly = df.groupby("year").pnl_rs.agg(["sum", "count", lambda s: (s > 0).mean()])
    yearly.columns = ["pnl", "trades", "win"]
    ins, oos = df[df.year < 2019], df[df.year >= 2019]
    sharpe = df.pnl_rs.mean() / df.pnl_rs.std() * SQ(52) if df.pnl_rs.std() else 0
    return dict(name=name, desc=desc, trades=int(len(df)), win_rate=float((df.pnl_rs > 0).mean()),
                avg_pnl_rs=float(df.pnl_rs.mean()), total_rs=float(df.pnl_rs.sum()),
                avg_win_rs=float(df[df.pnl_rs > 0].pnl_rs.mean()) if (df.pnl_rs > 0).any() else 0,
                avg_loss_rs=float(df[df.pnl_rs < 0].pnl_rs.mean()) if (df.pnl_rs < 0).any() else 0,
                worst_rs=float(df.pnl_rs.min()), best_rs=float(df.pnl_rs.max()), max_dd_rs=float(dd),
                profit_factor=float(wins / losses) if losses else None, sharpe_weekly_ann=float(sharpe),
                avg_risk_rs=float(df.risk_rs.mean()), return_on_risk_per_trade=float((df.pnl_rs / df.risk_rs).mean()),
                in_sample_2011_2018=dict(trades=int(len(ins)), avg=float(ins.pnl_rs.mean()) if len(ins) else 0, win=float((ins.pnl_rs > 0).mean()) if len(ins) else 0),
                out_of_sample_2019_now=dict(trades=int(len(oos)), avg=float(oos.pnl_rs.mean()) if len(oos) else 0, win=float((oos.pnl_rs > 0).mean()) if len(oos) else 0),
                last_52_trades=dict(avg=float(df.tail(52).pnl_rs.mean()), win=float((df.tail(52).pnl_rs > 0).mean()), total=float(df.tail(52).pnl_rs.sum())),
                yearly={int(y): dict(pnl=float(r.pnl), trades=int(r.trades), win=float(r.win)) for y, r in yearly.iterrows()},
                equity=[[t, round(float(v))] for t, v in zip(df.expiry, eq)][::2])


def ic(short=1.0, wing=1.75):
    return lambda S, s, r: [(-1, "P", S * math.exp(-short * s)), (1, "P", S * math.exp(-wing * s)),
                            (-1, "C", S * math.exp(short * s)), (1, "C", S * math.exp(wing * s))]


def strangle(short=1.0):
    return lambda S, s, r: [(-1, "P", S * math.exp(-short * s)), (-1, "C", S * math.exp(short * s))]


def trend_spread(short=0.8, wing=1.5):
    def f(S, s, r):
        if np.isnan(r.dma50):
            return []
        if r.close > r.dma50:
            return [(-1, "P", S * math.exp(-short * s)), (1, "P", S * math.exp(-wing * s))]
        return [(-1, "C", S * math.exp(short * s)), (1, "C", S * math.exp(wing * s))]
    return f


def long_straddle(S, s, r):
    return [(1, "P", S), (1, "C", S)]


def no_event(row, t0, e):
    return not any(t0 < d <= e for d in EVENT_SET)


def calm(row, t0, e, cap=22):
    return row.vix < cap and no_event(row, t0, e)


def calm_and_momentum(row, t0, e):
    i = P.index.get_loc(t0)
    vix5 = P.vix.iloc[i - 5]
    return calm(row, t0, e) and row.vix <= vix5 * 1.15


def macro_ok(row, t0, e):
    """Skip short-vol when overnight macro stress is building (US VIX up >25% in 20d, or INR -1.5%)."""
    i = P.index.get_loc(t0)
    usvix = P["lvl_US VIX"]; inr = P["lvl_USD/INR"]
    return calm(row, t0, e) and usvix.iloc[i] <= usvix.iloc[i - 20] * 1.25 and inr.iloc[i] <= inr.iloc[i - 20] * 1.015


STRATS = [
    ("Iron condor 1σ/1.75σ (every week)", ic(), None, "Sell ±1σ strangle, buy ±1.75σ wings, every week, no filter"),
    ("Short strangle 1σ naked (every week)", strangle(), None, "Unhedged ±1σ strangle: shows the tail risk SEBI warns about"),
    ("Iron condor + event & VIX<22 filter", ic(), calm, "Skip weeks with RBI/Budget/election, skip VIX ≥ 22"),
    ("Iron condor + filter + VIX not spiking", ic(), calm_and_momentum, "Above, and skip if VIX rose >15% in last 5 sessions"),
    ("Iron condor + macro guard", ic(), macro_ok, "Calm filter + skip if US VIX +25% or rupee −1.5% over 20 sessions"),
    ("Trend credit spread 0.8σ/1.5σ", trend_spread(), None, "Above 50-DMA: bull put spread; below: bear call spread"),
    ("Trend credit spread + macro guard", trend_spread(), macro_ok, "Trend spread only when the macro guard is green"),
    ("Wide iron condor 1.25σ/2σ + macro guard", ic(1.25, 2.0), macro_ok, "Further OTM strikes: higher win rate, smaller credit"),
    ("Long ATM straddle (every week)", lambda S, s, r: long_straddle(S, s, r), None, "Buying weekly options: the retail default"),
]
bt = []
for nm, fn, flt, desc in STRATS:
    _, df = run_strategy(nm, fn, flt)
    bt.append(summarise(nm, df, desc))

# event straddle: buy ATM straddle at close the day before the event, sell at event-day close.
ev_rows = []
for d in sorted(EVENT_SET):
    if d not in P.index:
        continue
    i = P.index.get_loc(d)
    if i < 2 or d.year < 2011:
        continue
    r0, r1 = P.iloc[i - 1], P.iloc[i]
    S0, S1 = r0.close, r1.close
    e = next((x for x in EXP if x >= d + pd.Timedelta(days=1)), None)
    if e is None:
        continue
    T0, T1 = max((e - P.index[i - 1]).days, 1) / 365, max((e - d).days, 0.5) / 365
    a0 = r0.vix / 100 * 1.05; a1 = r1.vix / 100 * 0.95
    c0 = bs(S0, S0, T0, a0, "C") + bs(S0, S0, T0, a0, "P")
    c1 = bs(S1, S0, T1, a1, "C") + bs(S1, S0, T1, a1, "P")
    net = (c1 - c0 - 2 * 0.75 * S0 / SCALE_SPOT - 0.0015 * c1) * SCALE_SPOT / S0 * LOT
    ev_rows.append(dict(entry=str(P.index[i - 1].date()), expiry=str(d.date()), pnl_rs=net, risk_rs=c0 * SCALE_SPOT / S0 * LOT,
                        vix=float(r0.vix), spot=S0, settle=S1, credit=-c0, pnl_pts=net / LOT))
bt.append(summarise("Event straddle (buy day before RBI/Budget/election)", pd.DataFrame(ev_rows),
                    "Long ATM straddle at prior close, exit event-day close; IV crush applied"))

# IV assumption sensitivity for the headline strategy
sens = []
for m in (0.85, 0.95, 1.05):
    _, df = run_strategy("ic", ic(), macro_ok, atm_mult=m)
    s = summarise("ic", df, "")
    sens.append(dict(atm_iv_vs_vix=m, avg_pnl_rs=s["avg_pnl_rs"], win_rate=s["win_rate"], max_dd_rs=s["max_dd_rs"],
                     profit_factor=s["profit_factor"]))
for m in (1.5, 3.0):
    _, df = run_strategy("ic", ic(), macro_ok, slip_pts=m)
    s = summarise("ic", df, "")
    sens.append(dict(slippage_pts_per_leg=m, avg_pnl_rs=s["avg_pnl_rs"], win_rate=s["win_rate"], max_dd_rs=s["max_dd_rs"],
                     profit_factor=s["profit_factor"]))

# ----------------------------------------------------------------------------- 6. trends
R = pd.DataFrame({"nifty": P.cc})
for k in ["S&P 500", "Nasdaq", "USD/INR", "Brent crude", "Gold", "US 10Y yield", "Dollar index (DXY)", "US VIX", "Bitcoin", "Copper"]:
    R[k] = P["x_" + k]          # overnight factor change vs NIFTY's next session (close-to-close)
for k in CONCURRENT:
    R[k] = P["c_" + k]
roll = {}
for k in R.columns[1:]:
    rc = R.nifty.rolling(252, min_periods=150).corr(R[k])
    r_last = rc.dropna()
    if r_last.empty:
        continue
    hist = rc[(rc.index >= rc.index[-1] - pd.Timedelta(days=3650))].dropna()
    q = R.nifty.tail(63).corr(R[k].tail(63))
    roll[k] = dict(corr_1y=float(r_last.iloc[-1]), corr_3m=float(q), corr_10y_avg=float(hist.mean()),
                   corr_10y_min=float(hist.min()), corr_10y_max=float(hist.max()),
                   shift_z=float((r_last.iloc[-1] - hist.mean()) / hist.std()) if hist.std() else 0,
                   series=[[str(d.date()), round(float(v), 3)] for d, v in rc.dropna().iloc[::21].items()])

yr = P[P.index >= "2011-01-01"].copy()
yr["year"] = yr.index.year
on_intr = []
for y, g in yr.groupby("year"):
    on = (1 + g.gap.fillna(0)).prod() - 1
    intr = (1 + g.oc.fillna(0)).prod() - 1
    tot = g.close.iloc[-1] / g.pc.iloc[0] - 1
    on_intr.append(dict(year=int(y), overnight=float(on * 100), intraday=float(intr * 100), total=float(tot * 100)))

P["rv21"] = P.cc.rolling(21).std().shift(-21) * SQ(252) * 100
vrp = []
for y, g in P[P.rv21.notna()].groupby(P[P.rv21.notna()].index.year):
    vrp.append(dict(year=int(y), avg_vix=float(g.vix.mean()), realised_vol=float(g.rv21.mean()),
                    premium=float(g.vix.mean() - g.rv21.mean()), pct_days_vix_above_rv=float((g.vix > g.rv21).mean())))

last = P.iloc[-1]
ath = P.close.max()
state = dict(
    date=str(P.index[-1].date()), nifty=float(last.close), vix=float(last.vix),
    vix_pct_rank_5y=float((P.vix[P.index >= P.index[-1] - pd.Timedelta(days=1826)] < last.vix).mean()),
    dma50=float(last.dma50), dma200=float(last.dma200), from_ath=float(last.close / ath - 1), ath=float(ath),
    repo=float(last.repo), repo_chg_6m=float(last.repo_chg_6m), us3m=float(last.fed), us3m_chg_6m_bps=float(last.fed_chg_6m),
    us10y=float(last["lvl_US 10Y yield"]), usdinr=float(last["lvl_USD/INR"]), brent=float(last["lvl_Brent crude"]),
    gold=float(last["lvl_Gold"]), dxy=float(last["lvl_Dollar index (DXY)"]),
    usdinr_chg20=float(chg20("USD/INR").iloc[-1] * 100), brent_chg20=float(chg20("Brent crude").iloc[-1] * 100),
    us10y_chg20_bps=float(chg20("US 10Y yield").iloc[-1]), usvix_chg20=float(chg20("US VIX").iloc[-1] * 100),
    ret_1m=float(P.close.iloc[-1] / P.close.iloc[-22] - 1), ret_3m=float(P.close.iloc[-1] / P.close.iloc[-64] - 1),
    ret_1y=float(P.close.iloc[-1] / P.close.iloc[-253] - 1), rv20=float(P.cc.tail(20).std() * SQ(252) * 100))

out = dict(generated=str(date.today()), data_through=state["date"], lot=LOT, scale_spot=SCALE_SPOT,
           factors_all=fac_all.round(4).to_dict("records"), factors_recent=fac_recent.round(4).to_dict("records"),
           concurrent_asia=conc, gap_model=gap_model, gap_follow=gap_follow, vix_regimes=vix_reg, trend=trend,
           macro=macro, cycles=cycles, day_of_week=dow, events=events, events_normal=events_normal,
           backtests=bt, sensitivity=sens, rolling_corr=roll, overnight_intraday=on_intr, vrp=vrp, state=state,
           rbi_history=RBI)


def clean(o):
    if isinstance(o, float):
        return None if (math.isnan(o) or math.isinf(o)) else round(o, 5)
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating,)):
        return clean(float(o))
    if isinstance(o, (np.integer,)):
        return int(o)
    return o


with open(os.path.join(HERE, "results.json"), "w") as f:
    json.dump(clean(out), f)
print("wrote results.json")
