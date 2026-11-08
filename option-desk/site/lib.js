// Option Desk maths: Black-Scholes, implied vol, NSE expiries, option-chain analytics.
// Pure functions, no DOM. Exposed on window.ODL.
(function () {
  const SQ = Math.sqrt, LN = Math.log, EXP = Math.exp;
  const RATE = 0.065;

  function ncdf(x) { // Abramowitz-Stegun 7.1.26 via erf, |err| < 1.5e-7
    const t = 1 / (1 + 0.3275911 * Math.abs(x) / SQ(2));
    const y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * EXP(-x * x / 2);
    return 0.5 * (1 + (x >= 0 ? y : -y));
  }
  const npdf = x => EXP(-x * x / 2) / SQ(2 * Math.PI);

  function bs(S, K, T, sig, type, r = RATE) {
    if (T <= 0 || sig <= 0) return Math.max(0, type === 'C' ? S - K : K - S);
    const d1 = (LN(S / K) + (r + sig * sig / 2) * T) / (sig * SQ(T)), d2 = d1 - sig * SQ(T);
    return type === 'C' ? S * ncdf(d1) - K * EXP(-r * T) * ncdf(d2) : K * EXP(-r * T) * ncdf(-d2) - S * ncdf(-d1);
  }

  function greeks(S, K, T, sig, type, r = RATE) {
    T = Math.max(T, 1e-6);
    const d1 = (LN(S / K) + (r + sig * sig / 2) * T) / (sig * SQ(T)), d2 = d1 - sig * SQ(T);
    const delta = type === 'C' ? ncdf(d1) : ncdf(d1) - 1;
    const gamma = npdf(d1) / (S * sig * SQ(T));
    const vega = S * npdf(d1) * SQ(T) / 100;
    const theta = (type === 'C'
      ? -S * npdf(d1) * sig / (2 * SQ(T)) - r * K * EXP(-r * T) * ncdf(d2)
      : -S * npdf(d1) * sig / (2 * SQ(T)) + r * K * EXP(-r * T) * ncdf(-d2)) / 365;
    return { price: bs(S, K, T, sig, type, r), delta, gamma, vega, theta };
  }

  function impliedVol(price, S, K, T, type, r = RATE) {
    let lo = 0.005, hi = 3;
    const intrinsic = Math.max(0, type === 'C' ? S - K : K - S);
    if (!(price > intrinsic) || T <= 0) return NaN;
    for (let i = 0; i < 80; i++) {
      const mid = (lo + hi) / 2;
      bs(S, K, T, mid, type, r) > price ? hi = mid : lo = mid;
    }
    return (lo + hi) / 2;
  }

  // Skew used in the backtest: OTM puts richer, OTM calls cheaper than ATM.
  function skewIV(K, S, atm, T) {
    const z = LN(K / S) / (atm * SQ(T));
    return Math.max(0.05, atm * (1 - 0.06 * z + 0.01 * z * z));
  }

  // ---------------------------------------------------------------- calendar
  const HOLIDAYS = new Set([
    '2026-01-15', '2026-01-26', '2026-03-03', '2026-03-26', '2026-03-31', '2026-04-03', '2026-04-14',
    '2026-05-01', '2026-05-28', '2026-06-26', '2026-09-14', '2026-10-02', '2026-10-20', '2026-11-10',
    '2026-11-24', '2026-12-25']);
  const HOLIDAYS_KNOWN_UNTIL = '2026-12-31';
  const FIXED = ['01-26', '05-01', '08-15', '10-02', '12-25'];
  const iso = d => d.toISOString().slice(0, 10);
  const addDays = (d, n) => { const x = new Date(d); x.setUTCDate(x.getUTCDate() + n); return x; };
  function isHoliday(d) {
    const s = iso(d);
    if (HOLIDAYS.has(s)) return true;
    return s > HOLIDAYS_KNOWN_UNTIL && FIXED.includes(s.slice(5));
  }
  const isTradingDay = d => d.getUTCDay() % 6 !== 0 && !isHoliday(d);
  function prevTradingDay(d) { let x = new Date(d); while (!isTradingDay(x)) x = addDays(x, -1); return x; }
  function istToday() { // calendar date in IST
    const n = new Date(Date.now() + 5.5 * 3600e3);
    return new Date(Date.UTC(n.getUTCFullYear(), n.getUTCMonth(), n.getUTCDate()));
  }
  function istNowMinutes() { const n = new Date(Date.now() + 5.5 * 3600e3); return n.getUTCHours() * 60 + n.getUTCMinutes(); }

  // NIFTY weekly expiry = Tuesday (previous trading day if holiday). Monthly = last Tuesday.
  function niftyExpiries(from, count = 6) {
    const out = [];
    let d = new Date(from);
    while (out.length < count) {
      if (d.getUTCDay() === 2) {
        const e = prevTradingDay(d);
        const nextTue = addDays(d, 7);
        const monthly = nextTue.getUTCMonth() !== d.getUTCMonth();
        const today = istToday();
        const past = iso(e) < iso(today) || (iso(e) === iso(today) && istNowMinutes() > 15 * 60 + 30);
        if (!past) out.push({ date: iso(e), weekday: e.toUTCString().slice(0, 3), monthly, moved: iso(e) !== iso(d) });
      }
      d = addDays(d, 1);
    }
    return out;
  }
  function tradingDaysBetween(a, b) { // sessions strictly after a up to and including b
    let n = 0, d = addDays(new Date(a), 1);
    while (iso(d) <= iso(b)) { if (isTradingDay(d)) n++; d = addDays(d, 1); }
    return n;
  }
  function nthSessionBefore(expiry, n) {
    let d = new Date(expiry), k = 0;
    while (k < n) { d = addDays(d, -1); if (isTradingDay(d)) k++; }
    return d;
  }
  // year fraction to 15:30 IST on expiry, from now
  function yearsTo(expiryIso) {
    const end = Date.parse(expiryIso + 'T10:00:00Z'); // 15:30 IST
    return Math.max((end - Date.now()) / 864e5, 0.02) / 365;
  }

  // ---------------------------------------------------------------- option chain
  function num(v) {
    if (v == null) return NaN;
    const s = String(v).replace(/[",\s]/g, '');
    if (s === '' || s === '-') return NaN;
    return Number(s);
  }
  function splitCSV(line) {
    const out = []; let cur = '', q = false;
    for (const ch of line) {
      if (ch === '"') q = !q; else if (ch === ',' && !q) { out.push(cur); cur = ''; } else cur += ch;
    }
    out.push(cur); return out.map(s => s.trim());
  }
  // Accepts NSE "Download (.csv)" (mirrored around STRIKE) or a simple CSV with
  // strike, call_oi, put_oi, call_chg_oi, put_chg_oi, call_ltp, put_ltp, call_iv, put_iv
  function parseChainCSV(text) {
    const lines = text.split(/\r?\n/).filter(l => l.trim());
    const rows = lines.map(splitCSV);
    const hi = rows.findIndex(r => r.some(c => c.toUpperCase() === 'STRIKE'));
    if (hi < 0) throw new Error('No STRIKE column found');
    const h = rows[hi].map(c => c.toUpperCase().replace(/\s+/g, ' ').trim());
    const sIdx = h.indexOf('STRIKE');
    const out = [];
    if (h.includes('CALL_OI') || h.includes('PUT_OI')) {
      const g = k => h.indexOf(k.toUpperCase());
      for (const r of rows.slice(hi + 1)) {
        const strike = num(r[sIdx]); if (!(strike > 0)) continue;
        out.push({ strike, call_oi: num(r[g('call_oi')]), put_oi: num(r[g('put_oi')]), call_chg_oi: num(r[g('call_chg_oi')]),
          put_chg_oi: num(r[g('put_chg_oi')]), call_ltp: num(r[g('call_ltp')]), put_ltp: num(r[g('put_ltp')]),
          call_iv: num(r[g('call_iv')]), put_iv: num(r[g('put_iv')]) });
      }
    } else {
      const left = k => h.slice(0, sIdx).indexOf(k);
      const right = k => { const i = h.slice(sIdx + 1).lastIndexOf(k); return i < 0 ? -1 : sIdx + 1 + i; };
      const c = { oi: left('OI'), chg: left('CHNG IN OI'), iv: left('IV'), ltp: left('LTP') };
      const p = { oi: right('OI'), chg: right('CHNG IN OI'), iv: right('IV'), ltp: right('LTP') };
      for (const r of rows.slice(hi + 1)) {
        const strike = num(r[sIdx]); if (!(strike > 0)) continue;
        out.push({ strike, call_oi: num(r[c.oi]), put_oi: num(r[p.oi]), call_chg_oi: num(r[c.chg]), put_chg_oi: num(r[p.chg]),
          call_ltp: num(r[c.ltp]), put_ltp: num(r[p.ltp]), call_iv: num(r[c.iv]), put_iv: num(r[p.iv]) });
      }
    }
    if (!out.length) throw new Error('No strike rows parsed');
    return out.sort((a, b) => a.strike - b.strike);
  }

  function analyseChain(rows, spot) {
    const z = v => (isFinite(v) ? v : 0);
    const tc = rows.reduce((s, r) => s + z(r.call_oi), 0), tp = rows.reduce((s, r) => s + z(r.put_oi), 0);
    const tcc = rows.reduce((s, r) => s + z(r.call_chg_oi), 0), tpc = rows.reduce((s, r) => s + z(r.put_chg_oi), 0);
    let maxPain = null, best = Infinity;
    for (const k of rows) {
      let pain = 0;
      for (const r of rows) pain += z(r.call_oi) * Math.max(0, k.strike - r.strike) + z(r.put_oi) * Math.max(0, r.strike - k.strike);
      if (pain < best) { best = pain; maxPain = k.strike; }
    }
    const by = (f, filt) => rows.filter(filt).reduce((a, r) => (z(r[f]) > z(a?.[f]) ? r : a), null);
    const callWall = by('call_oi', r => r.strike >= spot) || by('call_oi', () => true);
    const putWall = by('put_oi', r => r.strike <= spot) || by('put_oi', () => true);
    const callWrite = by('call_chg_oi', () => true), putWrite = by('put_chg_oi', () => true);
    const atm = rows.reduce((a, r) => (Math.abs(r.strike - spot) < Math.abs(a.strike - spot) ? r : a), rows[0]);
    const straddle = z(atm.call_ltp) + z(atm.put_ltp);
    const near = (pct, side) => rows.reduce((a, r) => {
      const tgt = spot * (1 + pct * side); return Math.abs(r.strike - tgt) < Math.abs(a.strike - tgt) ? r : a; }, rows[0]);
    const otmPut = near(0.03, -1), otmCall = near(0.03, 1);
    return {
      pcr: tc ? tp / tc : NaN, pcrChange: tcc ? tpc / tcc : NaN, maxPain, callWall: callWall?.strike, putWall: putWall?.strike,
      callWallOI: callWall?.call_oi, putWallOI: putWall?.put_oi, freshCall: callWrite?.strike, freshPut: putWrite?.strike,
      atm: atm.strike, straddle, atmCallIV: atm.call_iv, atmPutIV: atm.put_iv,
      skew: isFinite(otmPut.put_iv) && isFinite(otmCall.call_iv) ? otmPut.put_iv - otmCall.call_iv : NaN,
      totalCallOI: tc, totalPutOI: tp,
    };
  }

  // ---------------------------------------------------------------- payoff
  // legs: [{side:'BUY'|'SELL', type:'C'|'P', strike, premium, lots}]
  function payoffAt(legs, ST, lot) {
    return legs.reduce((s, l) => {
      const intr = Math.max(0, l.type === 'C' ? ST - l.strike : l.strike - ST);
      const q = (l.side === 'BUY' ? 1 : -1) * (l.lots || 1) * lot;
      return s + q * (intr - l.premium);
    }, 0);
  }
  function strategyStats(legs, S, sig, T, lot) {
    const ks = legs.map(l => l.strike);
    const lo = Math.min(S, ...ks) * 0.85, hi = Math.max(S, ...ks) * 1.15;
    const grid = []; for (let i = 0; i <= 600; i++) grid.push(lo + (hi - lo) * i / 600);
    const pts = grid.map(x => [x, payoffAt(legs, x, lot)]);
    const tail = [payoffAt(legs, 1, lot), payoffAt(legs, S * 5, lot)];
    const vals = pts.map(p => p[1]).concat(tail);
    const maxP = Math.max(...vals), maxL = Math.min(...vals);
    const unlimitedUp = payoffAt(legs, S * 5, lot) < payoffAt(legs, S * 4, lot) - 1;
    const be = [];
    for (let i = 1; i < pts.length; i++) {
      const [x0, y0] = pts[i - 1], [x1, y1] = pts[i];
      if ((y0 <= 0 && y1 > 0) || (y0 >= 0 && y1 < 0)) be.push(x0 + (x1 - x0) * (-y0) / (y1 - y0));
    }
    // probability of profit under lognormal with vol sig
    let pop = 0; const n = 2000;
    for (let i = 0; i < n; i++) {
      const u = (i + 0.5) / n; const zq = invNorm(u);
      const ST = S * EXP((RATE - sig * sig / 2) * T + sig * SQ(T) * zq);
      if (payoffAt(legs, ST, lot) > 0) pop++;
    }
    let net = { delta: 0, gamma: 0, theta: 0, vega: 0 };
    for (const l of legs) {
      const g = greeks(S, l.strike, T, sig, l.type); const q = (l.side === 'BUY' ? 1 : -1) * (l.lots || 1) * lot;
      net.delta += q * g.delta; net.gamma += q * g.gamma; net.theta += q * g.theta; net.vega += q * g.vega;
    }
    const credit = legs.reduce((s, l) => s + (l.side === 'SELL' ? 1 : -1) * l.premium * (l.lots || 1) * lot, 0);
    return { pts, maxP, maxL, unlimitedUp, unlimitedDown: payoffAt(legs, 1, lot) < -1e7, be, pop: pop / n, net, credit };
  }
  function invNorm(p) { // Acklam
    const a = [-39.69683028665376, 220.9460984245205, -275.9285104469687, 138.357751867269, -30.66479806614716, 2.506628277459239];
    const b = [-54.47609879822406, 161.5858368580409, -155.6989798598866, 66.80131188771972, -13.28068155288572];
    const c = [-0.007784894002430293, -0.3223964580411365, -2.400758277161838, -2.549732539343734, 4.374664141464968, 2.938163982698783];
    const d = [0.007784695709041462, 0.3224671290700398, 2.445134137142996, 3.754408661907416];
    const pl = 0.02425; let q, r;
    if (p < pl) { q = SQ(-2 * LN(p)); return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1); }
    if (p > 1 - pl) { q = SQ(-2 * LN(1 - p)); return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1); }
    q = p - 0.5; r = q * q;
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1);
  }

  // Indian round-trip charges for an options position held to expiry (₹), Apr-2026 rates.
  function charges(legs, lot, settle) {
    let sold = 0, bought = 0, itmLong = 0;
    for (const l of legs) {
      const v = l.premium * lot * (l.lots || 1);
      l.side === 'SELL' ? sold += v : bought += v;
      if (settle != null && l.side === 'BUY') itmLong += Math.max(0, l.type === 'C' ? settle - l.strike : l.strike - settle) * lot * (l.lots || 1);
    }
    const brokerage = 20 * legs.length * 1.18;
    const stt = 0.0015 * sold + 0.0015 * itmLong;
    const exch = (sold + bought) * 0.000355 * 1.18;
    const stamp = 0.00003 * bought;
    return { total: brokerage + stt + exch + stamp, brokerage, stt, exch, stamp };
  }

  window.ODL = { ncdf, bs, greeks, impliedVol, skewIV, niftyExpiries, tradingDaysBetween, nthSessionBefore, yearsTo,
    isTradingDay, istToday, iso, addDays, parseChainCSV, analyseChain, payoffAt, strategyStats, charges, HOLIDAYS_KNOWN_UNTIL };
})();
