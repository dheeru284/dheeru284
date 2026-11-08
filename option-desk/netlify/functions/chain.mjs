// GET /api/chain?symbol=NIFTY → NSE option chain, best effort.
// NSE often refuses requests from cloud data centres; the app then asks for the CSV
// from nseindia.com's option-chain page ("Download (.csv)") or a broker export.
const BASE = 'https://www.nseindia.com';
const H = {
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
  Accept: 'application/json,text/html;q=0.9,*/*;q=0.8', 'Accept-Language': 'en-IN,en;q=0.9', Referer: `${BASE}/option-chain`,
};

function cookies(res) {
  const list = typeof res.headers.getSetCookie === 'function' ? res.headers.getSetCookie() : [res.headers.get('set-cookie') || ''];
  return list.map(c => c.split(';')[0]).filter(Boolean).join('; ');
}

function normalise(j) {
  const recs = j.records || j.filtered || {};
  const data = (j.records?.data || j.filtered?.data || []);
  const expiry = j.records?.expiryDates?.[0] || j.records?.expiryDate;
  const rows = new Map();
  for (const d of data) {
    if (expiry && d.expiryDate && d.expiryDate !== expiry && d.expiryDates !== expiry) continue;
    const k = d.strikePrice;
    const r = rows.get(k) || { strike: k };
    if (d.CE) Object.assign(r, { call_oi: d.CE.openInterest, call_chg_oi: d.CE.changeinOpenInterest, call_ltp: d.CE.lastPrice, call_iv: d.CE.impliedVolatility });
    if (d.PE) Object.assign(r, { put_oi: d.PE.openInterest, put_chg_oi: d.PE.changeinOpenInterest, put_ltp: d.PE.lastPrice, put_iv: d.PE.impliedVolatility });
    rows.set(k, r);
  }
  return { underlying: recs.underlyingValue ?? j.records?.underlyingValue, timestamp: recs.timestamp, expiry, rows: [...rows.values()].sort((a, b) => a.strike - b.strike) };
}

export default async (req) => {
  const symbol = (new URL(req.url).searchParams.get('symbol') || 'NIFTY').toUpperCase().replace(/[^A-Z]/g, '');
  try {
    const home = await fetch(`${BASE}/option-chain`, { headers: H, signal: AbortSignal.timeout(7000) });
    const ck = cookies(home);
    const hdr = { ...H, Cookie: ck };
    let j;
    try {
      const info = await fetch(`${BASE}/api/option-chain-contract-info?symbol=${symbol}`, { headers: hdr, signal: AbortSignal.timeout(7000) }).then(r => r.json());
      const exp = info.expiryDates[0];
      j = await fetch(`${BASE}/api/option-chain-v3?type=Indices&symbol=${symbol}&expiry=${encodeURIComponent(exp)}`, { headers: hdr, signal: AbortSignal.timeout(8000) }).then(r => r.json());
      j.records = j.records || {}; j.records.expiryDates = [exp];
    } catch {
      j = await fetch(`${BASE}/api/option-chain-indices?symbol=${symbol}`, { headers: hdr, signal: AbortSignal.timeout(8000) }).then(r => r.json());
    }
    const out = normalise(j);
    if (!out.rows.length) throw new Error('NSE returned no rows');
    return new Response(JSON.stringify({ ok: true, symbol, ...out }), {
      headers: { 'content-type': 'application/json', 'cache-control': 'public, max-age=60', 'netlify-cdn-cache-control': 'public, s-maxage=120' },
    });
  } catch (e) {
    return new Response(JSON.stringify({ ok: false, error: `NSE blocked or changed its API (${e.message}). Upload the option-chain CSV instead.` }), {
      status: 502, headers: { 'content-type': 'application/json' },
    });
  }
};

export const config = { path: '/api/chain' };
