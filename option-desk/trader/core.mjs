// Auto-trader brain. One call to tick() = one decision cycle. Rules come from the backtest:
//   entry  : close of the 4th session before the Tuesday expiry (15:10–15:24 IST), gate not red,
//            real credit ≥ model credit at IV 0.90×VIX, size by risk %, half size on amber
//   stop   : loss ≥ STOP_MULT × credit at the close (15:15+); safety exit at HARD_STOP_MULT× anytime
//   target : hold to expiry (cash settlement). Optional PROFIT_TARGET (lowered returns in the test)
// Only positions it opened itself (managedBy:"auto") are ever touched.
import fs from 'node:fs';
import { getJSON, setJSON, del } from '../netlify/lib/store.mjs';
import { push } from '../netlify/lib/notify.mjs';
import { liveState, gate, planLegs, netCredit, nextTradeableExpiry, L } from '../netlify/lib/gate.mjs';
import { chart } from '../netlify/lib/yahoo.mjs';

const readJSON = rel => JSON.parse(fs.readFileSync(new URL(rel, import.meta.url), 'utf8'));
const EVENTS = () => readJSON('../site/events.json');
const BEST = (() => { try { return readJSON('../site/results.json').best_exit?.ic?.chosen; } catch { return null; } })();

export function config(env = process.env) {
  return {
    mode: (env.MODE || 'sim').toLowerCase(),
    lotsMax: Math.max(1, Number(env.LOTS_MAX || 1)),
    capital: Number(env.CAPITAL || 0),
    riskPct: Number(env.RISK_PCT || 2),
    maxMonthlyLoss: Number(env.MAX_MONTHLY_LOSS || 20000),
    stopMult: Number(env.STOP_MULT || (typeof BEST?.stop === 'number' ? BEST.stop : 1)),
    hardMult: Number(env.HARD_STOP_MULT || 1.5),
    target: env.PROFIT_TARGET ? Number(env.PROFIT_TARGET) : null,
    minCreditIv: 0.90,
  };
}

const ist = now => { const d = new Date(now + 5.5 * 3600e3); return { date: d.toISOString().slice(0, 10), min: d.getUTCHours() * 60 + d.getUTCMinutes() }; };
const tradingDay = date => L.isTradingDay(new Date(date + 'T00:00:00Z'));
const inMarket = t => tradingDay(t.date) && t.min >= 9 * 60 + 15 && t.min <= 15 * 60 + 30;
const rs = n => `${n < 0 ? '−' : ''}₹${Math.round(Math.abs(n)).toLocaleString('en-IN')}`;
const legName = l => `${l.side === 'SELL' ? 'S' : 'B'} ${l.strike}${l.type === 'C' ? 'CE' : 'PE'}`;

export async function log(ctx, level, title, body = '', extra = {}) {
  const e = { ts: new Date(ctx.now).toISOString(), level, title, body, ...extra };
  console.log(`[${e.ts}] ${level} ${title}${body ? ' — ' + body : ''}`);
  const all = await getJSON('auto-log', []);
  await setJSON('auto-log', [e, ...all].slice(0, 300));
  if (['TRADE', 'EXIT', 'ERROR', 'WARN', 'STOP', 'TARGET'].includes(level)) {
    await push({ level: level === 'TRADE' ? 'INFO' : level === 'ERROR' ? 'EXIT' : level, title: `[${ctx.cfg.mode.toUpperCase()}] ${title}`, body });
  }
}

// Mark to market with real quotes (mid). Returns ₹ P&L for the whole position.
async function mark(ctx, pos) {
  const q = await ctx.broker.quotes(pos.legs, pos.expiry);
  let pnl = 0;
  for (const l of pos.legs) {
    const x = q[l.token] || {}; const mid = x.bid && x.ask ? (x.bid + x.ask) / 2 : x.ltp;
    l.mark = mid;
    pnl += (l.side === 'SELL' ? l.premium - mid : mid - l.premium) * l.qty;
  }
  return pnl;
}

function chargesFor(legs, lot, settle) {
  return L.charges(legs.map(l => ({ side: l.side, type: l.type, strike: l.strike, premium: l.premium, lots: l.qty / lot })), lot, settle).total;
}

async function recordTrade(ctx, pos, exitLegs, reason, settle) {
  const gross = pos.legs.reduce((a, l, i) => a + (l.side === 'SELL' ? l.premium - exitLegs[i].price : exitLegs[i].price - l.premium) * l.qty, 0);
  const entryCh = chargesFor(pos.legs, pos.lot, settle);
  const exitCh = settle != null ? 0 : chargesFor(exitLegs.map((x, i) => ({ ...pos.legs[i], side: pos.legs[i].side === 'SELL' ? 'BUY' : 'SELL', premium: x.price })), pos.lot);
  const trade = { id: pos.id, mode: pos.mode, opened: pos.opened, closed: new Date(ctx.now).toISOString(), expiry: pos.expiry, structure: pos.structure,
    lots: pos.lots, lot: pos.lot, credit: pos.credit, spotIn: pos.spotAtEntry, spotOut: settle ?? pos.last?.spot ?? null, reason,
    legs: pos.legs.map((l, i) => ({ leg: legName(l), entry: l.premium, exit: exitLegs[i].price })),
    gross: Math.round(gross), charges: Math.round(entryCh + exitCh), pnl: Math.round(gross - entryCh - exitCh) };
  const trades = await getJSON('auto-trades', []);
  await setJSON('auto-trades', [trade, ...trades].slice(0, 500));
  await del('position');
  await log(ctx, trade.pnl >= 0 ? 'TARGET' : 'EXIT', `Closed (${reason}): ${rs(trade.pnl)}`,
    `${pos.lots} lot(s) ${pos.structure.toUpperCase()} ${pos.expiry}. Gross ${rs(trade.gross)}, charges ${rs(trade.charges)}.`);
  return trade;
}

export async function exitPosition(ctx, pos, reason) {
  // close shorts first (removes the risk), then sell the wings
  const order = [...pos.legs.map((l, i) => ({ l, i }))].sort((a, b) => (a.l.side === 'SELL' ? -1 : 1) - (b.l.side === 'SELL' ? -1 : 1));
  const orders = order.map(({ l }) => ({ ...l, side: l.side === 'SELL' ? 'BUY' : 'SELL' }));
  let fills;
  try { fills = await ctx.broker.execute(orders, pos.expiry); }
  catch (e) {
    await log(ctx, 'ERROR', 'EXIT FAILED: close the position manually in Angel One now', e.message);
    pos.exitError = e.message; await setJSON('position', pos);
    return null;
  }
  const exitLegs = [];
  order.forEach(({ i }, k) => { exitLegs[i] = { price: fills[k].fill }; });
  return recordTrade(ctx, pos, exitLegs, reason, null);
}

async function settleExpired(ctx, pos) {
  let settle = null;
  try {
    const c = await chart('^NSEI', '5d', '1d');
    settle = c.bars.find(b => b[0] === pos.expiry)?.[4] ?? null;
  } catch { /* fall through */ }
  if (settle == null) { try { settle = await ctx.broker.spot(); } catch { return; } }
  const exitLegs = pos.legs.map(l => ({ price: Math.max(0, l.type === 'C' ? settle - l.strike : l.strike - settle) }));
  return recordTrade(ctx, pos, exitLegs, `expiry settled at ${Math.round(settle)}`, settle);
}

async function tryEntry(ctx, t, status) {
  const ex = nextTradeableExpiry(t.date);
  const entryDay = L.iso(L.nthSessionBefore(new Date(ex.date + 'T00:00:00Z'), 4));
  status.nextEntry = { expiry: ex.date, entryDay };
  if (t.date !== entryDay || t.min < 15 * 60 + 10 || t.min > 15 * 60 + 24 || status.lastAttempt === t.date) return;
  status.lastAttempt = t.date;
  const cfg = ctx.cfg;
  const v = ctx.liveState ? await ctx.liveState() : await liveState();
  const g = gate(v, ex.date, EVENTS(), t.date);
  status.lastDecision = { date: t.date, expiry: ex.date, verdict: g.verdict, checks: g.checks };
  if (!g.structure) return log(ctx, 'INFO', `No trade for ${ex.date}: gate red`, g.checks.filter(c => c.st === 'bad').map(c => c.title).join('; '));

  const S = await ctx.broker.spot();
  const T = L.yearsTo(ex.date), atm = v.vix / 100 * 0.95;
  const legs = await ctx.broker.resolve(ex.date, planLegs(g.structure, S, atm, T));
  const q = await ctx.broker.quotes(legs, ex.date);
  const real = legs.reduce((a, l) => a + (l.side === 'SELL' ? (q[l.token]?.bid || 0) : -(q[l.token]?.ask || Infinity)), 0);
  const minCredit = netCredit(planLegs(g.structure, S, atm * cfg.minCreditIv / 0.95, T));
  if (!(real >= minCredit)) return log(ctx, 'INFO', `No trade for ${ex.date}: credit too low`, `Real credit ₹${real.toFixed(2)} < minimum ₹${minCredit.toFixed(2)} per unit.`);

  const lot = legs[0].lot;
  const width = Math.max(...['P', 'C'].map(ty => { const k = legs.filter(l => l.type === ty).map(l => l.strike); return Math.max(...k) - Math.min(...k); }));
  const maxLossLot = (width - real) * lot + 200;
  let lots = Math.min(cfg.lotsMax, Math.floor(cfg.capital * cfg.riskPct / 100 / maxLossLot));
  if (g.sizeFactor < 1) lots = Math.floor(lots * g.sizeFactor);
  if (lots < 1) return log(ctx, 'WARN', `No trade for ${ex.date}: capital too small`, `1 lot risks ${rs(maxLossLot)}; CAPITAL ${rs(cfg.capital)} × RISK_PCT ${cfg.riskPct}% allows less than one lot${g.sizeFactor < 1 ? ' at half size (amber gate)' : ''}.`);
  if (cfg.mode === 'live') {
    const f = await ctx.broker.funds();
    const avail = Number(f?.availablecash ?? f?.net ?? 0);
    if (avail < maxLossLot * lots * 1.3) return log(ctx, 'WARN', `No trade for ${ex.date}: insufficient funds`, `Available ${rs(avail)}, need about ${rs(maxLossLot * lots * 1.3)} margin.`);
  }
  const orders = [...legs].sort((a, b) => (a.side === 'BUY' ? -1 : 1) - (b.side === 'BUY' ? -1 : 1)).map(l => ({ ...l, qty: lots * lot }));
  let fills;
  try { fills = await ctx.broker.execute(orders, ex.date); }
  catch (e) { return log(ctx, 'ERROR', `Entry failed for ${ex.date}${e.partial?.length ? ' (filled legs were reversed)' : ''}`, e.message); }
  const pl = fills.map(f => ({ side: f.side, type: f.type, strike: f.strike, premium: f.fill, lots, qty: f.qty, symbol: f.symbol, token: f.token, lot: f.lot, tick: f.tick }));
  const creditU = pl.reduce((a, l) => a + (l.side === 'SELL' ? l.premium : -l.premium), 0);
  const pos = { id: Date.now(), managedBy: 'auto', mode: cfg.mode, opened: new Date(ctx.now).toISOString(), expiry: ex.date, structure: g.structure,
    legs: pl, lots, lot, credit: creditU * lot * lots, stopMult: cfg.stopMult, hardMult: cfg.hardMult, spotAtEntry: S, vixAtEntry: v.vix, ivMult: 0.95, gate: g.verdict };
  await setJSON('position', pos);
  await log(ctx, 'TRADE', `Entered ${g.structure === 'ic' ? 'iron condor' : 'wide condor'} ${ex.date}: credit ${rs(pos.credit)}`,
    `${pl.map(l => `${legName(l)} @${l.premium}`).join(', ')} · ${lots} lot(s). Stop ${rs(-cfg.stopMult * pos.credit)} at close, hard exit ${rs(-cfg.hardMult * cfg.stopMult * pos.credit)}. Target: hold to expiry.`);
}

export async function tick(ctx) {
  ctx.now = ctx.clock ? ctx.clock() : Date.now();
  const t = ist(ctx.now), cfg = ctx.cfg;
  const control = await getJSON('auto-control', { enabled: false });
  const status = await getJSON('auto-status', {});
  Object.assign(status, { beat: new Date(ctx.now).toISOString(), mode: cfg.mode, enabled: !!control.enabled,
    limits: { lotsMax: cfg.lotsMax, capital: cfg.capital, riskPct: cfg.riskPct, maxMonthlyLoss: cfg.maxMonthlyLoss, stopMult: cfg.stopMult, hardMult: cfg.hardMult, target: cfg.target } });
  let pos = await getJSON('position', null);
  if (pos && pos.managedBy !== 'auto') pos = null;      // never touch manually entered trades

  if (pos && (t.date > pos.expiry || (t.date === pos.expiry && t.min > 15 * 60 + 35))) { await settleExpired(ctx, pos); pos = null; }

  if (inMarket(t)) {
    if (pos && control.flatten) {
      await exitPosition(ctx, pos, 'manual exit from app'); pos = null;
      control.flatten = false; await setJSON('auto-control', control);
    }
    if (pos) {
      const pnl = await mark(ctx, pos);
      const stop = pos.stopMult * pos.credit, loss = -pnl;
      pos.last = { ts: new Date(ctx.now).toISOString(), spot: await ctx.broker.spot().catch(() => null), pnl: Math.round(pnl) };
      await setJSON('position', pos);
      if (loss >= pos.hardMult * stop) await exitPosition(ctx, pos, `hard stop (${rs(pnl)})`);
      else if (t.min >= 15 * 60 + 15 && loss >= stop) await exitPosition(ctx, pos, `stop at close (${rs(pnl)})`);
      else if (cfg.target && pnl >= cfg.target * pos.credit) await exitPosition(ctx, pos, `profit target (${rs(pnl)})`);
    } else if (control.enabled) {
      await tryEntry(ctx, t, status);
    }
  }
  if (control.flatten && !pos) { control.flatten = false; await setJSON('auto-control', control); }

  // monthly loss guard
  const trades = await getJSON('auto-trades', []);
  const month = t.date.slice(0, 7);
  const monthPnl = trades.filter(x => x.closed && new Date(Date.parse(x.closed) + 5.5 * 3600e3).toISOString().slice(0, 7) === month).reduce((a, x) => a + x.pnl, 0);
  status.monthPnl = monthPnl;
  if (control.enabled && monthPnl <= -cfg.maxMonthlyLoss) {
    control.enabled = false; control.disabledReason = `monthly loss ${rs(monthPnl)} hit the ${rs(cfg.maxMonthlyLoss)} limit`;
    await setJSON('auto-control', control);
    await log(ctx, 'WARN', 'Auto-trading paused: monthly loss limit', control.disabledReason);
  }
  await setJSON('auto-status', status);
  return { t, pos: await getJSON('position', null), status };
}
