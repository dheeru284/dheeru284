// Yahoo Finance chart API helpers (daily history and intraday), shared by functions and the trader.
export const SYMBOLS = {
  NIFTY: '^NSEI', BANKNIFTY: '^NSEBANK', INDIAVIX: '^INDIAVIX', 'S&P 500': '^GSPC', Nasdaq: '^IXIC',
  Dow: '^DJI', 'US VIX': '^VIX', 'Dollar index (DXY)': 'DX-Y.NYB', 'USD/INR': 'INR=X', 'Brent crude': 'BZ=F',
  Gold: 'GC=F', Silver: 'SI=F', Copper: 'HG=F', 'US 10Y yield': '^TNX', 'US 3M T-bill': '^IRX',
  DAX: '^GDAXI', 'FTSE 100': '^FTSE', Nikkei: '^N225', 'Hang Seng': '^HSI', Bitcoin: 'BTC-USD',
};

export async function chart(sym, range = '1y', interval = '1d') {
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(sym)}?range=${range}&interval=${interval}`;
  const r = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0 (OptionDesk)' }, signal: AbortSignal.timeout(9000) });
  if (!r.ok) throw new Error(`${sym} HTTP ${r.status}`);
  const j = (await r.json()).chart.result[0];
  const off = j.meta.gmtoffset || 0;
  const q = j.indicators.quote[0];
  const bars = [];
  (j.timestamp || []).forEach((t, i) => {
    if (q.close[i] == null) return;
    const d = new Date((t + off) * 1000).toISOString().slice(0, interval === '1d' ? 10 : 16);
    bars.push([d, q.open[i], q.high[i], q.low[i], q.close[i]]);
  });
  const map = new Map(bars.map(b => [b[0], b]));
  return {
    symbol: sym, bars: [...map.values()],
    price: j.meta.regularMarketPrice, time: j.meta.regularMarketTime ? new Date(j.meta.regularMarketTime * 1000).toISOString() : null,
    marketDate: j.meta.regularMarketTime ? new Date((j.meta.regularMarketTime + off) * 1000).toISOString().slice(0, 10) : null,
    prevClose: j.meta.chartPreviousClose, currency: j.meta.currency, exchange: j.meta.exchangeName,
  };
}

export async function fetchMany(names = Object.keys(SYMBOLS)) {
  const res = await Promise.allSettled(names.map(n => chart(SYMBOLS[n])));
  const data = {}, errors = {};
  res.forEach((r, i) => (r.status === 'fulfilled' ? (data[names[i]] = r.value) : (errors[names[i]] = String(r.reason))));
  return { fetched: new Date().toISOString(), data, errors };
}
