// Technical indicators and statistics. Pure functions over arrays of numbers
// or bars ({t, o, h, l, c, v}, oldest first). Missing values are NaN.
(function (TD) {
  'use strict';

  function sma(xs, n) {
    const out = new Array(xs.length).fill(NaN);
    let sum = 0;
    for (let i = 0; i < xs.length; i++) {
      sum += xs[i];
      if (i >= n) sum -= xs[i - n];
      if (i >= n - 1) out[i] = sum / n;
    }
    return out;
  }

  function ema(xs, n) {
    const out = new Array(xs.length).fill(NaN);
    const k = 2 / (n + 1);
    let prev = NaN;
    for (let i = 0; i < xs.length; i++) {
      if (isNaN(xs[i])) continue;
      if (isNaN(prev)) {
        // Seed with the SMA of the first n valid points.
        if (i >= n - 1) {
          let s = 0, ok = true;
          for (let j = i - n + 1; j <= i; j++) { if (isNaN(xs[j])) { ok = false; break; } s += xs[j]; }
          if (ok) { prev = s / n; out[i] = prev; }
        }
        continue;
      }
      prev = xs[i] * k + prev * (1 - k);
      out[i] = prev;
    }
    return out;
  }

  // Wilder's RSI.
  function rsi(closes, n = 14) {
    const out = new Array(closes.length).fill(NaN);
    if (closes.length <= n) return out;
    let gain = 0, loss = 0;
    for (let i = 1; i <= n; i++) {
      const d = closes[i] - closes[i - 1];
      if (d >= 0) gain += d; else loss -= d;
    }
    gain /= n; loss /= n;
    out[n] = loss === 0 ? 100 : 100 - 100 / (1 + gain / loss);
    for (let i = n + 1; i < closes.length; i++) {
      const d = closes[i] - closes[i - 1];
      gain = (gain * (n - 1) + Math.max(d, 0)) / n;
      loss = (loss * (n - 1) + Math.max(-d, 0)) / n;
      out[i] = loss === 0 ? 100 : 100 - 100 / (1 + gain / loss);
    }
    return out;
  }

  function macd(closes, fast = 12, slow = 26, signal = 9) {
    const ef = ema(closes, fast), es = ema(closes, slow);
    const line = closes.map((_, i) => ef[i] - es[i]);
    const sig = ema(line, signal);
    const hist = line.map((v, i) => v - sig[i]);
    return { line, signal: sig, hist };
  }

  function bollinger(closes, n = 20, k = 2) {
    const mid = sma(closes, n);
    const upper = [], lower = [];
    for (let i = 0; i < closes.length; i++) {
      if (isNaN(mid[i])) { upper.push(NaN); lower.push(NaN); continue; }
      let v = 0;
      for (let j = i - n + 1; j <= i; j++) v += (closes[j] - mid[i]) ** 2;
      const sd = Math.sqrt(v / n);
      upper.push(mid[i] + k * sd);
      lower.push(mid[i] - k * sd);
    }
    return { mid, upper, lower };
  }

  // Wilder's ATR.
  function atr(bars, n = 14) {
    const out = new Array(bars.length).fill(NaN);
    const tr = bars.map((b, i) => i === 0 ? b.h - b.l
      : Math.max(b.h - b.l, Math.abs(b.h - bars[i - 1].c), Math.abs(b.l - bars[i - 1].c)));
    if (bars.length < n) return out;
    let a = 0;
    for (let i = 0; i < n; i++) a += tr[i];
    a /= n;
    out[n - 1] = a;
    for (let i = n; i < bars.length; i++) { a = (a * (n - 1) + tr[i]) / n; out[i] = a; }
    return out;
  }

  // Rolling z-score of volume against the previous n days.
  function volumeZ(bars, n = 20) {
    const out = new Array(bars.length).fill(NaN);
    for (let i = n; i < bars.length; i++) {
      let m = 0;
      for (let j = i - n; j < i; j++) m += bars[j].v;
      m /= n;
      let v = 0;
      for (let j = i - n; j < i; j++) v += (bars[j].v - m) ** 2;
      const sd = Math.sqrt(v / n);
      out[i] = sd > 0 ? (bars[i].v - m) / sd : 0;
    }
    return out;
  }

  // Swing pivots (local highs/lows over +-w bars), clustered into levels within
  // tol (fraction of price). Returns [{price, touches, kind}] sorted by price.
  function levels(bars, w = 5, tol = 0.015) {
    const piv = [];
    for (let i = w; i < bars.length - w; i++) {
      let hi = true, lo = true;
      for (let j = i - w; j <= i + w; j++) {
        if (bars[j].h > bars[i].h) hi = false;
        if (bars[j].l < bars[i].l) lo = false;
      }
      if (hi) piv.push({ price: bars[i].h, kind: 'high' });
      if (lo) piv.push({ price: bars[i].l, kind: 'low' });
    }
    piv.sort((a, b) => a.price - b.price);
    const clusters = [];
    for (const p of piv) {
      const c = clusters[clusters.length - 1];
      if (c && Math.abs(p.price - c.price) / c.price <= tol) {
        c.sum += p.price; c.touches++; c.price = c.sum / c.touches;
      } else {
        clusters.push({ price: p.price, sum: p.price, touches: 1 });
      }
    }
    return clusters.map(c => ({ price: c.price, touches: c.touches }));
  }

  function logReturns(closes) {
    const r = [];
    for (let i = 1; i < closes.length; i++) {
      if (closes[i] > 0 && closes[i - 1] > 0) r.push(Math.log(closes[i] / closes[i - 1]));
    }
    return r;
  }

  function mean(xs) { return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : NaN; }
  function stdev(xs) {
    if (xs.length < 2) return NaN;
    const m = mean(xs);
    return Math.sqrt(xs.reduce((a, b) => a + (b - m) ** 2, 0) / (xs.length - 1));
  }
  // Percentile of an already sorted array, linear interpolation, p in [0, 100].
  function percentile(sorted, p) {
    if (!sorted.length) return NaN;
    const idx = (p / 100) * (sorted.length - 1);
    const lo = Math.floor(idx), hi = Math.ceil(idx);
    return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo);
  }

  // Deterministic PRNG so the same inputs reproduce the same simulation.
  function mulberry32(seed) {
    let a = seed >>> 0;
    return function () {
      a = (a + 0x6D2B79F5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function hashString(s) {
    let h = 2166136261;
    for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
    return h >>> 0;
  }

  TD.ind = { sma, ema, rsi, macd, bollinger, atr, volumeZ, levels, logReturns,
    mean, stdev, percentile, mulberry32, hashString };
})(window.TD = window.TD || {});
