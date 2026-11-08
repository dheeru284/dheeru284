// Server-side copies of the pricing used by the backtest and the app (keep in sync with site/lib.js).
const SQ = Math.sqrt, LN = Math.log, EXP = Math.exp;
export const RATE = 0.065;
export const LOT = 65;

function ncdf(x) {
  const t = 1 / (1 + 0.3275911 * Math.abs(x) / SQ(2));
  const y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * EXP(-x * x / 2);
  return 0.5 * (1 + (x >= 0 ? y : -y));
}
export function bs(S, K, T, sig, type, r = RATE) {
  if (T <= 0 || sig <= 0) return Math.max(0, type === 'C' ? S - K : K - S);
  const d1 = (LN(S / K) + (r + sig * sig / 2) * T) / (sig * SQ(T)), d2 = d1 - sig * SQ(T);
  return type === 'C' ? S * ncdf(d1) - K * EXP(-r * T) * ncdf(d2) : K * EXP(-r * T) * ncdf(-d2) - S * ncdf(-d1);
}
export function skewIV(K, S, atm, T) {
  const z = LN(K / S) / (atm * SQ(T));
  return Math.max(0.05, atm * (1 - 0.06 * z + 0.01 * z * z));
}
// years to 15:30 IST on expiry date (YYYY-MM-DD)
export const yearsTo = (expiry, now = Date.now()) => Math.max((Date.parse(expiry + 'T10:00:00Z') - now) / 864e5, 0.01) / 365;

// Mark a position to model. legs: [{side,type,strike,premium,lots}] premiums = actual fill prices.
// Returns ₹ P&L for the whole position and the cost to close per unit.
export function markPosition(pos, spot, vix, now = Date.now()) {
  const T = yearsTo(pos.expiry, now);
  const atm = vix / 100 * (pos.ivMult || 0.95);
  let pnl = 0, close = 0;
  for (const l of pos.legs) {
    const v = bs(spot, l.strike, T, skewIV(l.strike, spot, atm, T), l.type);
    const q = (l.side === 'BUY' ? 1 : -1) * (l.lots || 1);
    pnl += q * (v - l.premium) * LOT;
    close += -q * v;          // what it costs (per unit, all lots) to buy back shorts / sell longs
  }
  return { pnl, closeCost: close, T };
}

// NSE holidays (equity derivatives) — keep in sync with site/lib.js
const HOLIDAYS = new Set(['2026-11-10', '2026-11-24', '2026-12-25', '2027-01-26']);
export function istNow(now = Date.now()) {
  const d = new Date(now + 5.5 * 3600e3);
  return { date: d.toISOString().slice(0, 10), minutes: d.getUTCHours() * 60 + d.getUTCMinutes(), dow: d.getUTCDay() };
}
export function marketOpen(now = Date.now()) {
  const t = istNow(now);
  return t.dow >= 1 && t.dow <= 5 && !HOLIDAYS.has(t.date) && t.minutes >= 9 * 60 + 15 && t.minutes <= 15 * 60 + 30;
}
