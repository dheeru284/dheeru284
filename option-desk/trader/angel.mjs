// Minimal Angel One SmartAPI client (REST), written against angel-one/smartapi-javascript.
// Credentials come only from environment variables on YOUR server (see trader/.env.example).
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const ROOT = 'https://apiconnect.angelone.in';
const EP = {
  login: '/rest/auth/angelbroking/user/v1/loginByPassword',
  logout: '/rest/secure/angelbroking/user/v1/logout',
  profile: '/rest/secure/angelbroking/user/v1/getProfile',
  rms: '/rest/secure/angelbroking/user/v1/getRMS',
  place: '/rest/secure/angelbroking/order/v1/placeOrder',
  modify: '/rest/secure/angelbroking/order/v1/modifyOrder',
  cancel: '/rest/secure/angelbroking/order/v1/cancelOrder',
  details: '/rest/secure/angelbroking/order/v1/details',
  orderBook: '/rest/secure/angelbroking/order/v1/getOrderBook',
  positions: '/rest/secure/angelbroking/order/v1/getPosition',
  quote: '/rest/secure/angelbroking/market/v1/quote',
  margin: '/rest/secure/angelbroking/margin/v1/batch',
};
const SCRIP_MASTER = 'https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json';
export const NIFTY_INDEX_TOKEN = '99926000';   // NSE: NIFTY 50 index

// RFC 6238 TOTP from the base32 secret Angel shows when you enable TOTP.
export function totp(secret, now = Date.now()) {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  let bits = '';
  for (const ch of secret.replace(/=+$/, '').replace(/\s/g, '').toUpperCase()) {
    const v = alphabet.indexOf(ch); if (v < 0) throw new Error('bad TOTP secret');
    bits += v.toString(2).padStart(5, '0');
  }
  const key = Buffer.from(bits.match(/.{8}/g).map(b => parseInt(b, 2)));
  const counter = Buffer.alloc(8); counter.writeBigUInt64BE(BigInt(Math.floor(now / 1000 / 30)));
  const h = crypto.createHmac('sha1', key).update(counter).digest();
  const o = h[h.length - 1] & 0xf;
  const code = ((h[o] & 0x7f) << 24 | h[o + 1] << 16 | h[o + 2] << 8 | h[o + 3]) % 1e6;
  return String(code).padStart(6, '0');
}

export class Angel {
  constructor(env = process.env) {
    for (const k of ['ANGEL_API_KEY', 'ANGEL_CLIENT_CODE', 'ANGEL_PIN', 'ANGEL_TOTP_SECRET'])
      if (!env[k]) throw new Error(`${k} is not set`);
    this.env = env; this.jwt = null; this.loginAt = 0;
  }

  headers() {
    return {
      'Content-Type': 'application/json', Accept: 'application/json', 'X-UserType': 'USER', 'X-SourceID': 'WEB',
      'X-ClientLocalIP': this.env.ANGEL_LOCAL_IP || '127.0.0.1', 'X-ClientPublicIP': this.env.ANGEL_PUBLIC_IP || '127.0.0.1',
      'X-MACAddress': this.env.ANGEL_MAC || '00:00:00:00:00:00', 'X-PrivateKey': this.env.ANGEL_API_KEY,
      ...(this.jwt ? { Authorization: `Bearer ${this.jwt}` } : {}),
    };
  }

  async call(ep, body, method = 'POST') {
    const r = await fetch(ROOT + ep, { method, headers: this.headers(), body: body == null ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(10000) });
    const text = await r.text();
    let j; try { j = JSON.parse(text); } catch { throw new Error(`Angel ${ep} HTTP ${r.status}: ${text.slice(0, 200)}`); }
    if (j.status === false || (j.errorcode && j.errorcode !== '')) {
      if (/token|session|AG8001|AB1010/i.test(`${j.errorcode} ${j.message}`) && ep !== EP.login && !this._retry) {
        this._retry = true; try { await this.login(true); return await this.call(ep, body, method); } finally { this._retry = false; }
      }
      throw new Error(`Angel ${ep}: ${j.message || 'error'} (${j.errorcode || r.status})`);
    }
    return j.data;
  }

  async login(force = false) {
    if (this.jwt && !force && Date.now() - this.loginAt < 6 * 3600e3) return;
    this.jwt = null;
    const d = await this.call(EP.login, { clientcode: this.env.ANGEL_CLIENT_CODE, password: this.env.ANGEL_PIN, totp: totp(this.env.ANGEL_TOTP_SECRET) });
    this.jwt = d.jwtToken; this.loginAt = Date.now();
  }
  logout() { return this.call(EP.logout, { clientcode: this.env.ANGEL_CLIENT_CODE }).catch(() => {}); }
  profile() { return this.call(EP.profile, null, 'GET'); }
  funds() { return this.call(EP.rms, null, 'GET'); }
  positions() { return this.call(EP.positions, null, 'GET'); }
  orderBook() { return this.call(EP.orderBook, null, 'GET'); }
  orderDetails(uniqueOrderId) { return this.call(`${EP.details}/${uniqueOrderId}`, null, 'GET'); }

  // FULL quote: ltp + best bid/ask for NFO option tokens (max 50 per call).
  async quotes(tokens, exchange = 'NFO') {
    const d = await this.call(EP.quote, { mode: 'FULL', exchangeTokens: { [exchange]: tokens } });
    const out = {};
    for (const q of d?.fetched || []) {
      out[q.symbolToken] = { ltp: q.ltp, bid: q.depth?.buy?.[0]?.price || 0, ask: q.depth?.sell?.[0]?.price || 0, close: q.close };
    }
    return out;
  }
  async niftySpot() { const q = await this.quotes([NIFTY_INDEX_TOKEN], 'NSE'); return q[NIFTY_INDEX_TOKEN]?.ltp; }

  placeOrder({ symbol, token, side, qty, price }) {
    return this.call(EP.place, {
      variety: 'NORMAL', tradingsymbol: symbol, symboltoken: token, transactiontype: side, exchange: 'NFO',
      ordertype: 'LIMIT', producttype: 'CARRYFORWARD', duration: 'DAY', price: price.toFixed(2), quantity: String(qty),
      ordertag: 'optiondesk',
    });
  }
  modifyOrder({ orderid, symbol, token, qty, price }) {
    return this.call(EP.modify, { variety: 'NORMAL', orderid, ordertype: 'LIMIT', producttype: 'CARRYFORWARD', duration: 'DAY',
      price: price.toFixed(2), quantity: String(qty), tradingsymbol: symbol, symboltoken: token, exchange: 'NFO' });
  }
  cancelOrder(orderid) { return this.call(EP.cancel, { variety: 'NORMAL', orderid }); }
  margin(positions) { return this.call(EP.margin, { positions }); }
}

// NIFTY option contracts from Angel's public scrip master, cached per day.
export async function niftyOptions(cacheDir = os.tmpdir()) {
  const day = new Date(Date.now() + 5.5 * 3600e3).toISOString().slice(0, 10);
  const file = path.join(cacheDir, `angel-nifty-options-${day}.json`);
  if (fs.existsSync(file)) return JSON.parse(fs.readFileSync(file, 'utf8'));
  const r = await fetch(SCRIP_MASTER, { signal: AbortSignal.timeout(60000) });
  if (!r.ok) throw new Error(`scrip master HTTP ${r.status}`);
  const all = await r.json();
  const opts = all.filter(s => s.exch_seg === 'NFO' && s.instrumenttype === 'OPTIDX' && s.name === 'NIFTY')
    .map(s => ({ token: s.token, symbol: s.symbol, expiry: parseExpiry(s.expiry), strike: Number(s.strike) / 100,
      type: s.symbol.endsWith('CE') ? 'C' : 'P', lot: Number(s.lotsize), tick: Number(s.tick_size) / 100 || 0.05 }));
  fs.writeFileSync(file, JSON.stringify(opts));
  return opts;
}
function parseExpiry(s) { // "17NOV2026" → "2026-11-17"
  const m = /^(\d{2})([A-Z]{3})(\d{4})$/.exec(s || ''); if (!m) return null;
  const mon = 'JANFEBMARAPRMAYJUNJULAUGSEPOCTNOVDEC'.indexOf(m[2]) / 3 + 1;
  return `${m[3]}-${String(mon).padStart(2, '0')}-${m[1]}`;
}
export function findContract(opts, expiry, strike, type) {
  const c = opts.filter(o => o.expiry === expiry && o.type === type);
  if (!c.length) return null;
  return c.reduce((a, o) => (Math.abs(o.strike - strike) < Math.abs(a.strike - strike) ? o : a));
}
