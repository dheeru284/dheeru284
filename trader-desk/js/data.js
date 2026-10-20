// Data sources. Every fetch runs in the user's browser with the user's own
// free API key; nothing passes through a server we control.
// Bars come back oldest first as {t: 'YYYY-MM-DD', o, h, l, c, v}.
(function (TD) {
  'use strict';

  async function getJSON(url) {
    let res;
    try {
      res = await fetch(url);
    } catch (e) {
      throw new Error('Network error (offline, blocked, or the provider refused cross-origin requests).');
    }
    if (!res.ok) throw new Error('HTTP ' + res.status + ' from ' + new URL(url).host);
    return res.json();
  }

  function clean(bars) {
    return bars
      .filter(b => b.t && [b.o, b.h, b.l, b.c].every(x => isFinite(x) && x > 0))
      .map(b => ({ ...b, v: isFinite(b.v) ? b.v : 0 }))
      .sort((a, b) => a.t < b.t ? -1 : a.t > b.t ? 1 : 0);
  }

  // Twelve Data: free tier, up to 5000 daily bars, 8 req/min, 800/day.
  async function twelveData(symbol, key) {
    if (!key) throw new Error('No Twelve Data key. Add a free one in Settings.');
    const url = 'https://api.twelvedata.com/time_series?interval=1day&outputsize=600'
      + '&symbol=' + encodeURIComponent(symbol) + '&apikey=' + encodeURIComponent(key);
    const j = await getJSON(url);
    if (j.status === 'error') throw new Error('Twelve Data: ' + j.message);
    return clean((j.values || []).map(v => ({
      t: v.datetime.slice(0, 10), o: +v.open, h: +v.high, l: +v.low, c: +v.close, v: +v.volume,
    })));
  }

  // Alpha Vantage: free tier returns only the last 100 daily bars ("compact").
  async function alphaVantage(symbol, key) {
    if (!key) throw new Error('No Alpha Vantage key. Add a free one in Settings.');
    const url = 'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&outputsize=compact'
      + '&symbol=' + encodeURIComponent(symbol) + '&apikey=' + encodeURIComponent(key);
    const j = await getJSON(url);
    const series = j['Time Series (Daily)'];
    if (!series) throw new Error('Alpha Vantage: ' + (j['Error Message'] || j.Note || j.Information || 'no data'));
    return clean(Object.entries(series).map(([t, v]) => ({
      t, o: +v['1. open'], h: +v['2. high'], l: +v['3. low'], c: +v['4. close'], v: +v['5. volume'],
    })));
  }

  // Finnhub company news (free tier). Returns [{time, headline, source, summary, url}].
  async function finnhubNews(symbol, key, days = 14) {
    if (!key) throw new Error('No Finnhub key. News needs a free key from finnhub.io.');
    const to = new Date(), from = new Date(Date.now() - days * 864e5);
    const d = x => x.toISOString().slice(0, 10);
    const url = 'https://finnhub.io/api/v1/company-news?symbol=' + encodeURIComponent(symbol)
      + '&from=' + d(from) + '&to=' + d(to) + '&token=' + encodeURIComponent(key);
    const j = await getJSON(url);
    if (!Array.isArray(j)) throw new Error('Finnhub: ' + (j.error || 'unexpected response'));
    return j.map(n => ({
      time: new Date(n.datetime * 1000), headline: n.headline || '', source: n.source || '',
      summary: n.summary || '', url: n.url || '',
    }));
  }

  // CSV with a header row. Accepts Yahoo/Stooq/broker exports:
  // Date,Open,High,Low,Close[,Adj Close],Volume (column order may vary).
  function parseCSV(text) {
    const lines = text.trim().split(/\r?\n/).filter(Boolean);
    if (lines.length < 2) throw new Error('CSV has no data rows.');
    const head = lines[0].split(/[,;\t]/).map(h => h.trim().toLowerCase().replace(/"/g, ''));
    const col = name => head.findIndex(h => h === name || h.startsWith(name));
    const iT = col('date') >= 0 ? col('date') : col('time');
    const iO = col('open'), iH = col('high'), iL = col('low'), iV = col('vol');
    const iC = head.indexOf('close') >= 0 ? head.indexOf('close') : col('close');
    if ([iT, iO, iH, iL, iC].some(i => i < 0)) {
      throw new Error('CSV needs Date, Open, High, Low, Close columns. Found: ' + head.join(', '));
    }
    const num = s => +String(s).replace(/["$\s]/g, '');
    const bars = lines.slice(1).map(line => {
      const f = line.split(/[,;\t]/);
      const raw = String(f[iT]).replace(/"/g, '').trim();
      const dt = new Date(raw);
      const t = isNaN(dt) ? raw.slice(0, 10) : dt.toISOString().slice(0, 10);
      return { t, o: num(f[iO]), h: num(f[iH]), l: num(f[iL]), c: num(f[iC]), v: iV >= 0 ? num(f[iV]) : 0 };
    });
    const out = clean(bars);
    if (out.length < 30) throw new Error('CSV parsed to only ' + out.length + ' valid rows; need at least 30.');
    return out;
  }

  // Synthetic prices for trying the app without any key. Seeded by symbol so
  // it is reproducible. These are NOT real prices and the UI says so.
  function synthetic(symbol, n = 500) {
    const rnd = TD.ind.mulberry32(TD.ind.hashString(symbol.toUpperCase()));
    const gauss = () => {
      let u = 0, v = 0;
      while (u === 0) u = rnd();
      while (v === 0) v = rnd();
      return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
    };
    let p = 50 + rnd() * 250, vol = 0.018;
    const bars = [];
    const d = new Date();
    d.setDate(d.getDate() - Math.round(n * 1.45));
    while (bars.length < n) {
      d.setDate(d.getDate() + 1);
      if (d.getDay() === 0 || d.getDay() === 6) continue;
      vol = Math.min(0.05, Math.max(0.008, vol * (0.94 + 0.12 * rnd())));
      const r = 0.0003 + vol * gauss();
      const o = p * (1 + vol * 0.3 * gauss());
      const c = p * Math.exp(r);
      const h = Math.max(o, c) * (1 + Math.abs(vol * 0.5 * gauss()));
      const l = Math.min(o, c) * (1 - Math.abs(vol * 0.5 * gauss()));
      bars.push({ t: d.toISOString().slice(0, 10), o, h, l, c, v: Math.round(1e6 * (1 + 3 * rnd()) * (1 + 20 * Math.abs(r))) });
      p = c;
    }
    return bars;
  }

  TD.data = { twelveData, alphaVantage, finnhubNews, parseCSV, synthetic };
})(window.TD = window.TD || {});
