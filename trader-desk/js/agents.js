// The eleven desk agents. Each is a deterministic function: same inputs, same
// output. None of them predicts prices; they summarise data and do arithmetic.
(function (TD) {
  'use strict';
  const I = TD.ind;
  const last = xs => xs[xs.length - 1];

  // 1. Chart Scanner ---------------------------------------------------------
  function chartScanner(bars) {
    const c = bars.map(b => b.c);
    const sma20 = I.sma(c, 20), sma50 = I.sma(c, 50), sma200 = I.sma(c, 200);
    const rsi = I.rsi(c, 14), m = I.macd(c), bb = I.bollinger(c, 20, 2);
    const atr = I.atr(bars, 14), vz = I.volumeZ(bars, 20);
    const lv = I.levels(bars.slice(-250), 5, 0.015);
    const price = last(c), n = bars.length;

    const notes = [];
    let trend = 'Sideways';
    if (!isNaN(last(sma200))) {
      if (price > last(sma50) && last(sma50) > last(sma200)) trend = 'Uptrend';
      else if (price < last(sma50) && last(sma50) < last(sma200)) trend = 'Downtrend';
    } else if (!isNaN(last(sma50))) {
      trend = price > last(sma50) ? 'Above 50-day' : 'Below 50-day';
      notes.push('Fewer than 200 bars: 200-day average unavailable.');
    }
    for (let i = n - 1; i >= Math.max(1, n - 20); i--) {
      if (isNaN(sma200[i - 1])) break;
      if (sma50[i - 1] <= sma200[i - 1] && sma50[i] > sma200[i]) { notes.push('Golden cross (50 over 200) ' + (n - 1 - i) + ' bars ago.'); break; }
      if (sma50[i - 1] >= sma200[i - 1] && sma50[i] < sma200[i]) { notes.push('Death cross (50 under 200) ' + (n - 1 - i) + ' bars ago.'); break; }
    }
    let macdCross = null;
    for (let i = n - 1; i >= Math.max(1, n - 5); i--) {
      if (m.line[i - 1] <= m.signal[i - 1] && m.line[i] > m.signal[i]) { macdCross = 'bullish'; break; }
      if (m.line[i - 1] >= m.signal[i - 1] && m.line[i] < m.signal[i]) { macdCross = 'bearish'; break; }
    }
    if (macdCross) notes.push('MACD ' + macdCross + ' cross in the last 5 bars.');
    const r = last(rsi);
    if (r >= 70) notes.push('RSI ' + r.toFixed(1) + ': overbought zone.');
    else if (r <= 30) notes.push('RSI ' + r.toFixed(1) + ': oversold zone.');
    const bbPos = (price - last(bb.lower)) / (last(bb.upper) - last(bb.lower));
    if (bbPos > 1) notes.push('Closed above the upper Bollinger band.');
    if (bbPos < 0) notes.push('Closed below the lower Bollinger band.');

    const volSpikes = [];
    for (let i = Math.max(0, n - 20); i < n; i++) {
      if (vz[i] >= 2) volSpikes.push({ t: bars[i].t, z: vz[i], up: bars[i].c >= bars[i].o });
    }
    if (volSpikes.length) notes.push(volSpikes.length + ' volume anomaly day(s) (z >= 2) in the last 20 bars.');

    const below = lv.filter(l => l.price < price).sort((a, b) => b.price - a.price);
    const above = lv.filter(l => l.price > price).sort((a, b) => a.price - b.price);
    const yr = bars.slice(-252);
    const rets = I.logReturns(c.slice(-253));

    return {
      price, date: last(bars).t, trend, notes, macdCross,
      sma20: last(sma20), sma50: last(sma50), sma200: last(sma200),
      rsi: r, macd: last(m.line), macdSignal: last(m.signal), macdHist: last(m.hist),
      bbUpper: last(bb.upper), bbLower: last(bb.lower), bbPos,
      atr: last(atr), atrPct: last(atr) / price * 100,
      volZ: last(vz), volSpikes,
      support: below.slice(0, 3), resistance: above.slice(0, 3),
      high52: Math.max(...yr.map(b => b.h)), low52: Math.min(...yr.map(b => b.l)),
      annVol: I.stdev(rets) * Math.sqrt(252) * 100,
      series: { sma20, sma50, sma200, rsi, macd: m, bb },
    };
  }

  // 2. News Monitor ----------------------------------------------------------
  const IMPACT = [
    'earnings', 'guidance', 'outlook', 'downgrade', 'upgrade', 'fda', 'sec ', 'lawsuit', 'acquisition',
    'acquire', 'merger', 'recall', 'bankruptcy', 'layoff', 'ceo', 'cfo', 'investigation', 'probe',
    'split', 'buyback', 'repurchase', 'dividend', 'offering', 'antitrust', 'tariff', 'resign', 'delist',
  ];
  function newsMonitor(news) {
    const items = news.slice().sort((a, b) => b.time - a.time).map(n => {
      const text = (n.headline + ' ' + n.summary).toLowerCase();
      const tags = IMPACT.filter(k => text.includes(k)).map(k => k.trim());
      return { ...n, tags, high: tags.length > 0 };
    });
    return { items, highCount: items.filter(i => i.high).length };
  }

  // 8. Sentiment Analyzer (headline lexicon; crude by design) ----------------
  const POS = ['beat', 'beats', 'surge', 'soar', 'record', 'upgrade', 'raises', 'raised', 'strong', 'growth',
    'profit', 'gain', 'rally', 'outperform', 'bullish', 'approval', 'approved', 'wins', 'expands', 'tops', 'jumps', 'rises'];
  const NEG = ['miss', 'misses', 'plunge', 'falls', 'fall', 'drop', 'drops', 'downgrade', 'cut', 'cuts', 'weak',
    'loss', 'lawsuit', 'probe', 'investigation', 'recall', 'bearish', 'layoffs', 'decline', 'slump', 'warning',
    'warns', 'halt', 'fraud', 'delay', 'sinks', 'tumbles', 'lowers'];
  function sentiment(news) {
    if (!news.length) return { score: NaN, label: 'No data', pos: 0, neg: 0, neutral: 0, n: 0 };
    let pos = 0, neg = 0, neutral = 0, total = 0;
    for (const n of news) {
      const words = n.headline.toLowerCase().split(/[^a-z]+/);
      const s = words.filter(w => POS.includes(w)).length - words.filter(w => NEG.includes(w)).length;
      if (s > 0) pos++; else if (s < 0) neg++; else neutral++;
      total += Math.sign(s);
    }
    const score = total / news.length; // -1 .. +1
    const label = score > 0.15 ? 'Positive' : score < -0.15 ? 'Negative' : 'Mixed / neutral';
    return { score, label, pos, neg, neutral, n: news.length };
  }

  // 4. Exit Planner ----------------------------------------------------------
  function exitPlanner(entry, side, scan) {
    const a = scan.atr, dir = side === 'short' ? -1 : 1;
    const why = [];
    let stop;
    const structure = dir > 0 ? scan.support.find(l => l.price < entry) : scan.resistance.find(l => l.price > entry);
    if (structure && Math.abs(entry - structure.price) <= 3 * a) {
      stop = structure.price - dir * 0.25 * a;
      why.push('Stop 0.25 ATR beyond ' + (dir > 0 ? 'support' : 'resistance') + ' at ' + structure.price.toFixed(2) + ' (' + structure.touches + ' touches).');
    } else {
      stop = entry - dir * 2 * a;
      why.push('No ' + (dir > 0 ? 'support' : 'resistance') + ' within 3 ATR; stop set at 2 ATR (' + (2 * a).toFixed(2) + ').');
    }
    if (Math.abs(entry - stop) < 1.0 * a) {
      stop = entry - dir * 1.0 * a;
      why.push('Widened to the 1 ATR minimum so normal daily noise does not trip it.');
    }
    const R = Math.abs(entry - stop);
    let target;
    const obstacle = dir > 0 ? scan.resistance.find(l => l.price > entry) : scan.support.find(l => l.price < entry);
    if (obstacle && Math.abs(obstacle.price - entry) >= 1.5 * R) {
      target = obstacle.price - dir * 0.1 * a;
      why.push('Target just before ' + (dir > 0 ? 'resistance' : 'support') + ' at ' + obstacle.price.toFixed(2) + '.');
    } else {
      target = entry + dir * 2 * R;
      why.push(obstacle ? 'Nearest ' + (dir > 0 ? 'resistance' : 'support') + ' is under 1.5R away, a cap on upside; target set at 2R.'
        : 'No overhead level in range; target set at 2R.');
    }
    const target2 = entry + dir * Math.max(3 * R, Math.abs(target - entry) + R);
    return { stop, target, target2, R, rr: Math.abs(target - entry) / R, why };
  }

  // 3. Entry Timer -----------------------------------------------------------
  function entryTimer(scan, side, entry, exit) {
    const dir = side === 'short' ? -1 : 1, p = scan.price, a = scan.atr;
    const checks = [];
    const add = (ok, text, w = 1) => checks.push({ ok, text, w });
    if (!isNaN(scan.sma50)) add(dir * (p - scan.sma50) > 0, 'Price ' + (dir > 0 ? 'above' : 'below') + ' 50-day average');
    if (!isNaN(scan.sma200)) add(dir * (scan.sma50 - scan.sma200) > 0, '50-day ' + (dir > 0 ? 'above' : 'below') + ' 200-day');
    add(dir > 0 ? scan.rsi > 40 && scan.rsi < 68 : scan.rsi < 60 && scan.rsi > 32,
      'RSI ' + scan.rsi.toFixed(1) + ' has room (not stretched)');
    add(dir * (scan.macd - scan.macdSignal) > 0, 'MACD ' + (dir > 0 ? 'above' : 'below') + ' signal line');
    const lvl = dir > 0 ? scan.support[0] : scan.resistance[0];
    add(!!lvl && Math.abs(entry - lvl.price) <= 1.0 * a, 'Entry within 1 ATR of ' + (dir > 0 ? 'support' : 'resistance'));
    add(Math.abs(entry - p) <= 1.5 * a, 'Entry within 1.5 ATR of last close (realistic fill)', 0.5);
    add(exit.rr >= 2, 'Reward:risk >= 2 (' + exit.rr.toFixed(2) + ')');

    const max = checks.reduce((s, c) => s + c.w, 0);
    const score = checks.reduce((s, c) => s + (c.ok ? c.w : 0), 0);
    const pct = score / max;

    // Two candidate entries: a pullback zone and a breakout trigger.
    const zone = dir > 0
      ? [Math.max(lvl ? lvl.price : -Infinity, scan.sma20 - 0.5 * a), Math.max(scan.sma20, lvl ? lvl.price : 0)]
      : [Math.min(scan.sma20, lvl ? lvl.price : Infinity), Math.min(lvl ? lvl.price : Infinity, scan.sma20 + 0.5 * a)];
    const brk = dir > 0 ? scan.resistance[0] : scan.support[0];
    return {
      checks, score, max, pct,
      grade: pct >= 0.75 ? 'Strong confluence' : pct >= 0.5 ? 'Partial confluence' : 'Weak confluence',
      pullback: zone.map(x => +x.toFixed(2)).sort((x, y) => x - y),
      breakout: brk ? brk.price + dir * 0.1 * a : null,
    };
  }

  // 5. Risk Manager ----------------------------------------------------------
  function riskManager(o) {
    const riskDollars = o.account * o.riskPct / 100;
    const warnings = [];
    let qty, maxLoss, posValue, unit;
    if (o.instrument === 'stock') {
      unit = 'shares';
      const per = Math.abs(o.entry - o.stop);
      qty = Math.floor(riskDollars / per);
      const cap = o.account * o.maxPosPct / 100;
      if (qty * o.entry > cap) {
        qty = Math.floor(cap / o.entry);
        warnings.push('Position capped at ' + o.maxPosPct + '% of account; risk is now below your ' + o.riskPct + '% budget.');
      }
      posValue = qty * o.entry;
      maxLoss = qty * per;
      if (per < 1.0 * o.atr) warnings.push('Stop is inside 1 ATR: likely to be hit by normal noise.');
      warnings.push('Stop loss assumes a fill at the stop. Overnight gaps can fill worse.');
    } else {
      unit = 'contracts';
      const perContract = o.premium * 100;
      qty = Math.floor(riskDollars / perContract);
      posValue = qty * perContract;
      maxLoss = posValue;
      if (qty === 0) warnings.push('One contract costs $' + perContract.toFixed(0) + ', more than your $' + riskDollars.toFixed(0) + ' risk budget. Size is 0.');
      warnings.push('Long options can lose 100% of premium; size treats the whole premium as at risk.');
    }
    if (o.riskPct > 2) warnings.push('Risk above 2% per trade: a 10-trade losing streak costs ' + (100 - 100 * Math.pow(1 - o.riskPct / 100, 10)).toFixed(0) + '% of the account.');
    if (o.exposure + posValue > o.account) warnings.push('Open positions plus this trade exceed account size (' + ((o.exposure + posValue) / o.account * 100).toFixed(0) + '% gross exposure).');
    if (o.heldAlready) warnings.push('You already hold ' + o.symbol + ' in the Portfolio tab: this adds concentration.');
    return { qty, unit, riskDollars, maxLoss, posValue, pctOfAccount: posValue / o.account * 100, warnings };
  }

  // 6. Time Machine: Monte Carlo by bootstrapping historical daily returns ---
  function timeMachine(o) {
    const closes = o.bars.map(b => b.c);
    let rets = I.logReturns(closes.slice(-(o.lookback + 1)));
    if (rets.length < 60) throw new Error('Need at least 60 daily returns; have ' + rets.length + '.');
    const mu = I.mean(rets);
    if (o.drift === 'zero') rets = rets.map(r => r - mu);
    const rnd = I.mulberry32(I.hashString([o.symbol, o.entry, o.stop, o.target, o.horizon, o.sims, o.drift, o.instrument].join('|')));
    const N = rets.length, dir = o.side === 'short' ? -1 : 1;
    const pnl = new Float64Array(o.sims), dd = new Float64Array(o.sims);
    let hitStop = 0, hitTarget = 0, expired = 0, daysSum = 0;

    for (let s = 0; s < o.sims; s++) {
      let S = o.entry, peak = 0, maxdd = 0, outcome = 0, d = 0;
      for (d = 1; d <= o.horizon; d++) {
        S *= Math.exp(rets[Math.floor(rnd() * N)]);
        if (o.instrument !== 'stock') continue;
        const u = dir * (S - o.entry);
        if (u > peak) peak = u;
        if (peak - u > maxdd) maxdd = peak - u;
        if (dir * (S - o.stop) <= 0) { outcome = -1; break; }
        if (dir * (S - o.target) >= 0) { outcome = 1; break; }
      }
      daysSum += Math.min(d, o.horizon);
      if (o.instrument === 'stock') {
        pnl[s] = dir * (S - o.entry) * o.qty;
        dd[s] = maxdd * o.qty;
        if (outcome === -1) hitStop++; else if (outcome === 1) hitTarget++; else expired++;
      } else {
        const intrinsic = o.instrument === 'call' ? Math.max(S - o.strike, 0) : Math.max(o.strike - S, 0);
        pnl[s] = (intrinsic - o.premium) * 100 * o.qty;
        if (intrinsic === 0) hitStop++;
        else if (intrinsic >= 2 * o.premium) hitTarget++;
        else expired++;
      }
    }
    const sorted = Array.from(pnl).sort((a, b) => a - b);
    const ddSorted = Array.from(dd).sort((a, b) => a - b);
    const wins = sorted.filter(x => x > 0).length;
    return {
      sims: o.sims, horizon: o.horizon, returnsUsed: N, dailyVol: I.stdev(rets), driftRemoved: o.drift === 'zero', histDrift: mu,
      winRate: wins / o.sims, avg: I.mean(sorted), median: I.percentile(sorted, 50),
      p5: I.percentile(sorted, 5), p95: I.percentile(sorted, 95), worst: sorted[0], best: last(sorted),
      pStop: hitStop / o.sims, pTarget: hitTarget / o.sims, pNeither: expired / o.sims,
      maxDDavg: o.instrument === 'stock' ? I.mean(ddSorted) : NaN,
      maxDD95: o.instrument === 'stock' ? I.percentile(ddSorted, 95) : NaN,
      avgDays: daysSum / o.sims, pnl: sorted,
    };
  }

  // 10. Backtester -----------------------------------------------------------
  const STRATEGIES = {
    sma_cross: 'SMA 20/50 crossover',
    rsi_revert: 'RSI(14) mean reversion: buy < 30, sell > 55',
    macd_cross: 'MACD 12/26/9 signal cross',
    breakout: 'Donchian breakout: 20-day high in, 10-day low out',
  };
  function backtest(bars, o) {
    const c = bars.map(b => b.c), n = bars.length;
    const s20 = I.sma(c, 20), s50 = I.sma(c, 50), r = I.rsi(c, 14), m = I.macd(c), a = I.atr(bars, 14);
    const start = Math.max(60, n - Math.round(o.months * 21));
    if (start >= n - 20) throw new Error('Not enough history for a ' + o.months + '-month test (have ' + n + ' bars).');
    const hh = (i, k) => Math.max(...bars.slice(i - k, i).map(b => b.h));
    const ll = (i, k) => Math.min(...bars.slice(i - k, i).map(b => b.l));
    const entrySig = i => ({
      sma_cross: s20[i - 1] <= s50[i - 1] && s20[i] > s50[i],
      rsi_revert: r[i] < 30,
      macd_cross: m.line[i - 1] <= m.signal[i - 1] && m.line[i] > m.signal[i],
      breakout: c[i] > hh(i, 20),
    })[o.strategy];
    const exitSig = i => ({
      sma_cross: s20[i] < s50[i],
      rsi_revert: r[i] > 55,
      macd_cross: m.line[i] < m.signal[i],
      breakout: c[i] < ll(i, 10),
    })[o.strategy];
    const cost = o.costBps / 1e4;
    let eq = 1, peak = 1, maxDD = 0, pos = null, pending = null;
    const trades = [], curve = [];
    for (let i = start; i < n; i++) {
      const b = bars[i];
      if (pending === 'buy' && !pos) {
        const px = b.o * (1 + cost), risk = o.stopAtr * a[i - 1];
        pos = { entry: px, t: b.t, stop: px - risk, tp: o.tpAtr > 0 ? px + o.tpAtr * a[i - 1] : Infinity, units: eq / px, risk };
      } else if (pending === 'sell' && pos) {
        close(b.o, b.t, 'signal');
      }
      pending = null;
      if (pos) {
        // Same-bar stop and target: assume the stop came first (conservative).
        if (b.l <= pos.stop) close(Math.min(b.o, pos.stop), b.t, 'stop');
        else if (b.h >= pos.tp) close(Math.max(b.o, pos.tp), b.t, 'target');
      }
      const mark = pos ? pos.units * b.c : eq;
      curve.push({ t: b.t, eq: mark });
      if (mark > peak) peak = mark;
      maxDD = Math.max(maxDD, (peak - mark) / peak);
      if (i < n - 1) {
        if (!pos && entrySig(i)) pending = 'buy';
        else if (pos && exitSig(i)) pending = 'sell';
      }
    }
    if (pos) close(bars[n - 1].c, bars[n - 1].t, 'open at end');

    function close(px, t, why) {
      px *= (1 - cost);
      const ret = px / pos.entry - 1;
      trades.push({ in: pos.t, out: t, entry: pos.entry, exit: px, ret, R: (px - pos.entry) / pos.risk, why });
      eq = pos.units * px;
      pos = null;
    }
    const wins = trades.filter(t => t.ret > 0), losses = trades.filter(t => t.ret <= 0);
    const gp = wins.reduce((s, t) => s + t.ret, 0), gl = -losses.reduce((s, t) => s + t.ret, 0);
    const days = n - start;
    return {
      strategy: STRATEGIES[o.strategy], from: bars[start].t, to: bars[n - 1].t, days,
      trades, totalReturn: eq - 1, cagr: Math.pow(eq, 252 / days) - 1, maxDD,
      winRate: trades.length ? wins.length / trades.length : NaN,
      profitFactor: gl > 0 ? gp / gl : (gp > 0 ? Infinity : NaN),
      avgR: trades.length ? I.mean(trades.map(t => t.R)) : NaN,
      buyHold: c[n - 1] / bars[start].o - 1, curve,
    };
  }

  // 7. Portfolio Tracker -----------------------------------------------------
  function portfolio(positions, cash) {
    const rows = positions.map(p => ({ ...p, value: p.shares * p.price, pnl: (p.price - p.cost) * p.shares }));
    const invested = rows.reduce((s, r) => s + r.value, 0), total = invested + (cash || 0);
    const hasTargets = rows.some(r => r.target > 0);
    const warnings = [];
    for (const r of rows) {
      r.weight = total ? r.value / total * 100 : 0;
      r.drift = hasTargets ? r.weight - (r.target || 0) : NaN;
      r.trade = hasTargets && r.price ? ((r.target || 0) / 100 * total - r.value) / r.price : NaN;
      if (r.weight > 25) warnings.push(r.symbol + ' is ' + r.weight.toFixed(1) + '% of the portfolio (over 25%).');
    }
    const tsum = rows.reduce((s, r) => s + (r.target || 0), 0);
    if (hasTargets && Math.abs(tsum - 100) > 0.5) warnings.push('Targets sum to ' + tsum.toFixed(1) + '%, not 100% (the rest is treated as cash).');
    const top3 = rows.map(r => r.weight).sort((a, b) => b - a).slice(0, 3).reduce((s, w) => s + w, 0);
    if (rows.length > 3 && top3 > 60) warnings.push('Top 3 holdings are ' + top3.toFixed(0) + '% of the portfolio.');
    return { rows, invested, total, cash: cash || 0, warnings, hasTargets };
  }

  // 9. Trade Journal ---------------------------------------------------------
  function journalStats(trades) {
    const closed = trades.filter(t => isFinite(t.exit) && t.exit > 0).map(t => {
      const dir = t.side === 'short' ? -1 : 1;
      const pnl = dir * (t.exit - t.entry) * t.size;
      const R = t.stop > 0 ? pnl / (Math.abs(t.entry - t.stop) * t.size) : NaN;
      return { ...t, pnl, R };
    });
    const group = {};
    for (const t of closed) (group[t.setup || 'untagged'] = group[t.setup || 'untagged'] || []).push(t);
    const summarize = ts => {
      const w = ts.filter(t => t.pnl > 0);
      const Rs = ts.map(t => t.R).filter(isFinite);
      return { n: ts.length, winRate: ts.length ? w.length / ts.length : NaN, pnl: ts.reduce((s, t) => s + t.pnl, 0), avgR: Rs.length ? I.mean(Rs) : NaN };
    };
    return {
      closed, all: summarize(closed), open: trades.length - closed.length,
      bySetup: Object.entries(group).map(([k, v]) => ({ setup: k, ...summarize(v) })).sort((a, b) => b.pnl - a.pnl),
    };
  }

  // 11. Alert System ---------------------------------------------------------
  const ALERT_TYPES = {
    price_above: 'Price closes above', price_below: 'Price closes below',
    rsi_above: 'RSI(14) above', rsi_below: 'RSI(14) below',
    pct_move: 'Daily move larger than (%)', news_keyword: 'Headline contains',
  };
  function checkAlerts(alerts, symbol, scan, bars, news) {
    const fired = [];
    const prev = bars.length > 1 ? bars[bars.length - 2].c : NaN;
    for (const a of alerts) {
      if (a.symbol !== symbol) continue;
      let hit = false, detail = '';
      switch (a.type) {
        case 'price_above': hit = scan.price > a.value; detail = 'close ' + scan.price.toFixed(2); break;
        case 'price_below': hit = scan.price < a.value; detail = 'close ' + scan.price.toFixed(2); break;
        case 'rsi_above': hit = scan.rsi > a.value; detail = 'RSI ' + scan.rsi.toFixed(1); break;
        case 'rsi_below': hit = scan.rsi < a.value; detail = 'RSI ' + scan.rsi.toFixed(1); break;
        case 'pct_move': {
          const mv = (scan.price / prev - 1) * 100;
          hit = Math.abs(mv) > a.value; detail = 'move ' + mv.toFixed(2) + '%'; break;
        }
        case 'news_keyword': {
          const h = news.find(n => n.headline.toLowerCase().includes(String(a.value).toLowerCase()));
          hit = !!h; detail = h ? h.headline : ''; break;
        }
      }
      if (hit) fired.push({ alert: a, detail });
    }
    return fired;
  }

  // Desk summary: turns agent outputs into one setup-quality call. -----------
  function deskCall(entryT, tm, sent, news) {
    const reasons = [];
    let pts = 0;
    if (entryT.pct >= 0.75) { pts += 2; reasons.push('technical confluence strong (' + entryT.score + '/' + entryT.max + ')'); }
    else if (entryT.pct >= 0.5) { pts += 1; reasons.push('technical confluence partial (' + entryT.score + '/' + entryT.max + ')'); }
    else reasons.push('technical confluence weak (' + entryT.score + '/' + entryT.max + ')');
    if (tm) {
      if (tm.avg > 0 && tm.median > 0) { pts += 1; reasons.push('simulated mean and median P&L both positive'); }
      else if (tm.avg <= 0) reasons.push('simulated mean P&L not positive');
      if (tm.pStop > 0.5) { pts -= 1; reasons.push('simulated stop-out/expire-worthless rate ' + (tm.pStop * 100).toFixed(0) + '%'); }
    }
    if (news && news.highCount > 0) reasons.push(news.highCount + ' high-impact headline(s): event risk');
    if (sent && sent.label === 'Negative') { pts -= 1; reasons.push('headline sentiment negative'); }
    const level = pts >= 3 ? 'High' : pts >= 1 ? 'Medium' : 'Low';
    return { level, reasons };
  }

  TD.agents = { chartScanner, newsMonitor, sentiment, exitPlanner, entryTimer, riskManager, timeMachine,
    backtest, STRATEGIES, portfolio, journalStats, ALERT_TYPES, checkAlerts, deskCall };
})(window.TD = window.TD || {});
