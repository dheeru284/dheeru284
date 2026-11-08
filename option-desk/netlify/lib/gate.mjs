// Server-side trade gate and plan: the same rules as the Today tab (site/app.js gateChecks /
// buildLegs), used by the auto-trader. Keep the two in sync.
import { L } from './odl.mjs';
import { fetchMany } from './yahoo.mjs';

const NEED = ['NIFTY', 'INDIAVIX', 'US VIX', 'USD/INR', 'US 10Y yield', 'Brent crude'];

export async function liveState() {
  const m = await fetchMany(NEED);
  for (const k of ['NIFTY', 'INDIAVIX', 'US VIX', 'USD/INR']) if (!m.data[k]) throw new Error(`missing ${k}: ${m.errors[k]}`);
  const d = m.data;
  const closes = d.NIFTY.bars.map(b => b[4]);
  const sma = n => closes.slice(-n).reduce((a, b) => a + b, 0) / Math.min(n, closes.length);
  const vixC = d.INDIAVIX.bars.map(b => b[4]);
  const vix = d.INDIAVIX.price ?? vixC[vixC.length - 1];
  const chg20 = {};
  for (const k of ['US VIX', 'USD/INR', 'US 10Y yield', 'Brent crude']) {
    const s = d[k]; if (!s) continue;
    const b = s.bars, p = s.price ?? b[b.length - 1][4], c20 = b.length > 21 ? b[b.length - 21][4] : NaN;
    chg20[k] = k.includes('yield') ? (p - c20) * 100 : p / c20 - 1;
  }
  const rets = closes.slice(-21).map((c, i, a) => (i ? Math.log(c / a[i - 1]) : null)).filter(v => v != null);
  const mu = rets.reduce((a, b) => a + b, 0) / rets.length;
  return {
    nifty: d.NIFTY.price ?? closes[closes.length - 1], vix, vixChg5: vixC.length > 6 ? vix / vixC[vixC.length - 6] - 1 : NaN,
    dma50: sma(50), dma200: sma(200), chg20,
    rv20: Math.sqrt(rets.reduce((a, b) => a + (b - mu) ** 2, 0) / (rets.length - 1) * 252), fetched: m.fetched,
  };
}

export function gate(v, expiry, events, today = L.iso(L.istToday())) {
  const entry = L.iso(L.nthSessionBefore(new Date(expiry + 'T00:00:00Z'), 4));
  const winStart = entry < today ? today : entry;
  const evIn = events.filter(e => e.date >= winStart && e.date <= expiry);
  const c = [];
  const add = (st, title) => c.push({ st, title });
  const hard = evIn.filter(e => e.kind !== 'FOMC');
  add(hard.length ? 'bad' : 'good', hard.length ? `event in window: ${hard.map(e => e.name).join(', ')}` : 'no RBI/Budget/election in window');
  if (evIn.some(e => e.kind === 'FOMC')) add('warn', 'FOMC in window');
  add(v.vix < 22 ? 'good' : v.vix < 30 ? 'warn' : 'bad', `India VIX ${v.vix.toFixed(2)}`);
  if (isFinite(v.vixChg5)) add(v.vixChg5 <= 0.15 ? 'good' : 'bad', `India VIX ${(v.vixChg5 * 100).toFixed(1)}% / 5 sessions`);
  add(v.chg20['US VIX'] <= 0.25 ? 'good' : 'bad', `US VIX ${(v.chg20['US VIX'] * 100).toFixed(1)}% / 20 sessions`);
  add(v.chg20['USD/INR'] <= 0.015 ? 'good' : 'bad', `USD/INR ${(v.chg20['USD/INR'] * 100).toFixed(2)}% / 20 sessions`);
  if (isFinite(v.chg20['US 10Y yield'])) add(v.chg20['US 10Y yield'] < 40 ? 'good' : 'warn', `US 10Y ${v.chg20['US 10Y yield'].toFixed(0)} bp / 20 sessions`);
  if (isFinite(v.chg20['Brent crude'])) add(v.chg20['Brent crude'] < 0.15 ? 'good' : 'warn', `Brent ${(v.chg20['Brent crude'] * 100).toFixed(1)}% / 20 sessions`);
  const bad = c.filter(x => x.st === 'bad').length, warn = c.filter(x => x.st === 'warn').length;
  const verdict = bad ? 'bad' : warn > 1 ? 'warn' : 'good';
  return { verdict, structure: verdict === 'good' ? 'ic' : verdict === 'warn' ? 'wide' : null, sizeFactor: verdict === 'good' ? 1 : 0.5, checks: c, entry, expiry };
}

// Strikes and model premiums (identical to buildLegs in app.js).
export function planLegs(structure, S, atm, T) {
  const sT = atm * Math.sqrt(T), r50 = k => Math.round(k / 50) * 50;
  const [a, b] = structure === 'wide' ? [1.25, 2] : [1, 1.75];
  return [['SELL', 'P', r50(S * Math.exp(-a * sT))], ['BUY', 'P', r50(S * Math.exp(-b * sT))],
    ['SELL', 'C', r50(S * Math.exp(a * sT))], ['BUY', 'C', r50(S * Math.exp(b * sT))]]
    .map(([side, type, strike]) => ({ side, type, strike, premium: +L.bs(S, strike, T, L.skewIV(strike, S, atm, T), type).toFixed(2) }));
}

export const netCredit = legs => legs.reduce((a, l) => a + (l.side === 'SELL' ? 1 : -1) * l.premium, 0);

// The next expiry whose backtest entry day is today or later.
export function nextTradeableExpiry(today = L.iso(L.istToday())) {
  const ex = L.niftyExpiries(new Date(today + 'T00:00:00Z'), 4);
  return ex.find(e => L.iso(L.nthSessionBefore(new Date(e.date + 'T00:00:00Z'), 4)) >= today) || ex[0];
}
export { L };
