// Brokers with one interface: spot(), quotes(legs), execute(orders), funds().
//   SimBroker   – no account: Yahoo spot + Black-Scholes prices with a spread. For testing anywhere.
//   PaperBroker – real Angel quotes, fills simulated at bid/ask. No orders are sent.
//   LiveBroker  – real Angel orders: marketable LIMIT orders, re-priced a few ticks, then cancelled.
import { Angel, niftyOptions, findContract } from './angel.mjs';
import { L } from '../netlify/lib/odl.mjs';
import { chart } from '../netlify/lib/yahoo.mjs';

const round = (p, tick = 0.05) => Math.max(tick, Math.round(p / tick) * tick);
const sleep = ms => new Promise(r => setTimeout(r, ms));

export class SimBroker {
  constructor(opts = {}) { this.mode = 'sim'; this.spread = opts.spread ?? 0.5; this.ivMult = 0.95; this.override = opts.override || null; }
  async market() {
    if (this.override) return this.override();
    const [n, v] = await Promise.all([chart('^NSEI', '1d', '5m'), chart('^INDIAVIX', '1d', '5m')]);
    return { spot: n.price, vix: v.price };
  }
  async spot() { return (await this.market()).spot; }
  async resolve(expiry, legs) {
    return legs.map(l => ({ ...l, symbol: `NIFTY${expiry.replace(/-/g, '')}${l.strike}${l.type === 'C' ? 'CE' : 'PE'}`, token: `${l.type}${l.strike}`, lot: 65, tick: 0.05 }));
  }
  async quotes(legs, expiry) {
    const { spot, vix } = await this.market();
    const T = L.yearsTo(expiry), atm = vix / 100 * this.ivMult, out = {};
    for (const l of legs) {
      const mid = L.bs(spot, l.strike, T, L.skewIV(l.strike, spot, atm, T), l.type);
      out[l.token] = { ltp: mid, bid: Math.max(0.05, mid - this.spread / 2), ask: mid + this.spread / 2 };
    }
    return out;
  }
  async execute(orders, expiry) {
    const q = await this.quotes(orders, expiry);
    return orders.map(o => ({ ...o, fill: round(o.side === 'BUY' ? q[o.token].ask : q[o.token].bid), orderId: `sim-${Date.now()}-${o.token}` }));
  }
  async funds() { return { net: null, availablecash: null, note: 'simulation' }; }
}

export class PaperBroker extends SimBroker {
  constructor(env) { super(); this.mode = 'paper'; this.angel = new Angel(env); this.opts = null; }
  async login() { await this.angel.login(); }
  async spot() { await this.login(); return this.angel.niftySpot(); }
  async market() { const [spot, v] = await Promise.all([this.spot(), chart('^INDIAVIX', '1d', '5m')]); return { spot, vix: v.price }; }
  async resolve(expiry, legs) {
    this.opts = this.opts || await niftyOptions();
    return legs.map(l => {
      const c = findContract(this.opts, expiry, l.strike, l.type);
      if (!c) throw new Error(`no NIFTY ${expiry} ${l.strike}${l.type} contract in scrip master`);
      if (c.strike !== l.strike) l = { ...l, strike: c.strike };
      return { ...l, symbol: c.symbol, token: c.token, lot: c.lot, tick: c.tick };
    });
  }
  async quotes(legs) { await this.login(); return this.angel.quotes(legs.map(l => l.token)); }
  async execute(orders) {
    const q = await this.quotes(orders);
    return orders.map(o => {
      const x = q[o.token]; const px = o.side === 'BUY' ? (x.ask || x.ltp) : (x.bid || x.ltp);
      return { ...o, fill: round(px, o.tick), orderId: `paper-${Date.now()}-${o.token}` };
    });
  }
  async funds() { await this.login(); return this.angel.funds(); }
}

export class LiveBroker extends PaperBroker {
  constructor(env) { super(env); this.mode = 'live'; this.maxSteps = Number(env.REPRICE_STEPS || 4); }
  // Executes sequentially (wings before shorts on entry; shorts before wings on exit). If any leg
  // fails, the legs already filled are reversed so you are never left with a naked short.
  async execute(orders) {
    await this.login();
    const done = [];
    for (const o of orders) {
      try { done.push(await this.fillOne(o)); }
      catch (e) {
        if (e.partialFill) done.push(e.partialFill);
        const undo = done.map(d => ({ ...d, side: d.side === 'BUY' ? 'SELL' : 'BUY' })).reverse();
        for (const u of undo) { try { await this.fillOne(u, 10); } catch (e2) { e.message += ` | UNWIND FAILED for ${u.symbol}: ${e2.message}`; } }
        e.partial = done; throw e;
      }
    }
    return done;
  }
  async fillOne(o, steps = this.maxSteps) {
    const q = (await this.angel.quotes([o.token]))[o.token];
    const tick = o.tick || 0.05;
    let px = round(o.side === 'BUY' ? (q.ask || q.ltp * 1.02) : (q.bid || q.ltp * 0.98), tick);
    const placed = await this.angel.placeOrder({ symbol: o.symbol, token: o.token, side: o.side, qty: o.qty, price: px });
    const uid = placed.uniqueorderid, oid = placed.orderid;
    for (let i = 0; i <= steps; i++) {
      for (let k = 0; k < 6; k++) {
        await sleep(1000);
        const d = await this.angel.orderDetails(uid);
        const st = (d.orderstatus || d.status || '').toLowerCase();
        if (st === 'complete') return { ...o, fill: Number(d.averageprice) || px, orderId: oid };
        if (st === 'rejected' || st === 'cancelled') throw new Error(`${o.side} ${o.symbol} ${st}: ${d.text || ''}`);
      }
      if (i === steps) break;
      px = round(px + (o.side === 'BUY' ? 2 : -2) * tick, tick);
      await this.angel.modifyOrder({ orderid: oid, symbol: o.symbol, token: o.token, qty: o.qty, price: px });
    }
    await this.angel.cancelOrder(oid).catch(() => {});
    const e = new Error(`${o.side} ${o.symbol} not filled after ${steps} re-prices (last ₹${px})`);
    const d = await this.angel.orderDetails(uid).catch(() => ({}));
    const filled = Number(d.filledshares || 0);
    if (filled > 0) e.partialFill = { ...o, qty: filled, fill: Number(d.averageprice) || px, orderId: oid };
    throw e;
  }
}

export function makeBroker(env = process.env) {
  const mode = (env.MODE || 'sim').toLowerCase();
  if (mode === 'live') return new LiveBroker(env);
  if (mode === 'paper') return new PaperBroker(env);
  return new SimBroker();
}
