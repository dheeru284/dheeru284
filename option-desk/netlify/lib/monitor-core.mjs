// Live monitor: watches NIFTY, India VIX, the open position and breaking news, and raises
// alerts (stored for the app, pushed to the phone). Called by the scheduled function every
// 2 minutes and on demand from the app ("Run check now").
import { getJSON, setJSON } from './store.mjs';
import { push } from './notify.mjs';
import { markPosition, istNow, marketOpen } from './quant.mjs';
import { fetchAll, HIGH_IMPACT } from './news-core.mjs';

const PUSH_LEVELS = new Set(['EXIT', 'STOP', 'WARN', 'TARGET', 'TEST']);
const fmt = n => Math.round(n).toLocaleString('en-IN');
const rs = n => `${n < 0 ? '−' : ''}₹${fmt(Math.abs(n))}`;

async function intraday(sym) {
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(sym)}?range=1d&interval=5m`;
  const r = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0 (OptionDesk monitor)' }, signal: AbortSignal.timeout(8000) });
  if (!r.ok) throw new Error(`${sym} ${r.status}`);
  const j = (await r.json()).chart.result[0];
  const closes = (j.indicators.quote[0].close || []).filter(v => v != null);
  return { price: j.meta.regularMarketPrice, prevClose: j.meta.chartPreviousClose ?? j.meta.previousClose, closes,
    time: j.meta.regularMarketTime * 1000 };
}

export async function runMonitor({ force = false, now = Date.now(), siteUrl = '' } = {}) {
  const t = istNow(now);
  const open = marketOpen(now);
  const state = await getJSON('state', { seen: [], last: {} });
  const pos = await getJSON('position', null);
  const out = [];
  const add = (level, key, title, body, coolMin = 30) => {
    const last = state.last[key];
    if (last && now - last < coolMin * 60e3) return;
    state.last[key] = now;
    out.push({ ts: new Date(now).toISOString(), level, key, title, body, url: siteUrl || undefined });
  };

  let nifty = null, vix = null, move15 = 0, vix15 = 0;
  if (open || force) {
    try {
      [nifty, vix] = await Promise.all([intraday('^NSEI'), intraday('^INDIAVIX')]);
      const n = nifty.closes, v = vix.closes;
      move15 = n.length > 3 ? n[n.length - 1] / n[n.length - 4] - 1 : 0;
      vix15 = v.length > 3 ? v[v.length - 1] / v[v.length - 4] - 1 : 0;
      const day = nifty.price / nifty.prevClose - 1, vday = vix.price / vix.prevClose - 1;
      // ---- market shock checks
      if (open && Math.abs(day) >= 0.012) add('WARN', `day-${Math.sign(day)}`, `NIFTY ${(day * 100).toFixed(2)}% today (${fmt(nifty.price)})`,
        'A >1.2% day is a top-10% move. Check open positions and the news tab.', 90);
      if (open && Math.abs(move15) >= 0.006) add('WARN', `fast-${Math.sign(move15)}`, `Fast move: NIFTY ${(move15 * 100).toFixed(2)}% in 15 min`,
        `Now ${fmt(nifty.price)}. Sudden moves often follow news; see the latest headlines.`, 30);
      if (open && vday >= 0.10) add('WARN', 'vix-spike', `India VIX +${(vday * 100).toFixed(1)}% today (${vix.price.toFixed(2)})`,
        'Volatility expanding: short-premium positions lose value even if NIFTY is flat. The backtest skipped new trades after VIX +15% in 5 sessions.', 120);
    } catch (e) { out.push({ ts: new Date(now).toISOString(), level: 'INFO', key: 'data', title: 'Price feed error', body: e.message, silent: true }); }
  }

  // ---- position checks
  if (pos && nifty && vix && pos.expiry >= t.date) {
    const m = markPosition(pos, nifty.price, vix.price, now);
    const stop = pos.stopMult * pos.credit;
    const loss = -m.pnl;
    const nearClose = t.minutes >= 15 * 60 + 10;
    const shorts = pos.legs.filter(l => l.side === 'SELL');
    pos.last = { ts: new Date(now).toISOString(), spot: nifty.price, vix: vix.price, pnl: Math.round(m.pnl) };
    if (loss >= 1.5 * stop) {
      add('EXIT', 'hardstop', `EXIT NOW: loss ${rs(loss)} is 1.5× your stop`, `NIFTY ${fmt(nifty.price)}, VIX ${vix.price.toFixed(2)}. Close all legs at market. Safety rule; the backtested stop is ${rs(stop)}.`, 15);
    } else if (loss >= stop) {
      if (nearClose) add('EXIT', 'stop-close', `EXIT: stop hit at the close (${rs(-loss)})`, `Backtested rule: exit when the loss reaches 1× the credit (${rs(stop)}). NIFTY ${fmt(nifty.price)}. Close all legs before 3:30 PM.`, 30);
      else add('WARN', 'stop-touch', `Stop level touched: ${rs(-loss)} (stop ${rs(stop)})`, `The backtested stop acts at the close (3:10–3:25 PM). Exit then if the loss is still ≥ ${rs(stop)}; exit immediately if it reaches ${rs(1.5 * stop)}.`, 30);
    }
    for (const l of shorts) {
      const breached = l.type === 'P' ? nifty.price < l.strike : nifty.price > l.strike;
      const progress = (nifty.price - pos.spotAtEntry) / (l.strike - pos.spotAtEntry);
      if (breached) add(nearClose ? 'EXIT' : 'WARN', `breach-${l.type}${l.strike}`, `NIFTY ${fmt(nifty.price)} is beyond your short ${l.strike} ${l.type === 'C' ? 'CE' : 'PE'}`,
        `Trend is against the position. P&L ${rs(m.pnl)}. ${nearClose ? 'Close all legs now.' : 'If it closes beyond this strike, exit.'}`, 45);
      else if ((l.type === 'P' ? l.strike < pos.spotAtEntry : l.strike > pos.spotAtEntry) && progress >= 0.7 && progress < 1) add('WARN', `near-${l.type}${l.strike}`, `NIFTY approaching your short ${l.strike} ${l.type === 'C' ? 'CE' : 'PE'} (${fmt(nifty.price)})`,
        `Covered ${Math.round(progress * 100)}% of the distance from entry. P&L ${rs(m.pnl)}. Watch the stop.`, 60);
    }
    if (t.date === pos.expiry && t.minutes >= 15 * 60 && m.pnl > 0) add('TARGET', 'expiry-target', `Expiry: position at ${rs(m.pnl)}`,
      'Target reached by holding to expiry (the backtested target). Index options settle in cash at the close.', 600);
    await setJSON('position', pos);
  }

  // ---- news: every run in market hours, every ~30 min otherwise
  if (open || force || t.minutes % 30 < 2) {
    try {
      const { items } = await fetchAll();
      const seen = new Set(state.seen);
      const fresh = items.filter(i => !seen.has(i.key) && now - Date.parse(i.date) < 3 * 3600e3);
      const firstRun = state.seen.length === 0;
      let n = 0;
      for (const i of fresh) {
        const big = (HIGH_IMPACT.test(i.title) && Math.abs(i.sentiment) >= 1) || Math.abs(i.sentiment) >= 3;
        if (!big || firstRun || n >= 3) continue;
        const reacting = open && (Math.abs(move15) >= 0.0035 || vix15 >= 0.03);
        const posNote = pos && pos.expiry >= t.date ? ' You have an open position: check the stop and strike distance.' : '';
        add(reacting ? 'WARN' : 'INFO', `news-${i.key}`, `${reacting ? 'Market reacting: ' : 'News: '}${i.title}`,
          `${i.source} · tone ${i.sentiment > 0 ? '+' : ''}${i.sentiment} · ${i.tags.join(', ') || 'general'}${reacting ? ` · NIFTY ${(move15 * 100).toFixed(2)}% / VIX ${(vix15 * 100).toFixed(1)}% in 15 min.` : ''}${posNote}\n${i.link}`, 600);
        n++;
      }
      state.seen = [...items.map(i => i.key), ...state.seen].slice(0, 600);
    } catch (e) { /* news is best-effort */ }
  }

  // ---- deliver
  const pushed = [];
  for (const a of out) {
    if (a.silent || !PUSH_LEVELS.has(a.level) && !(a.level === 'INFO' && process.env.PUSH_INFO === '1')) continue;
    const r = await push(a); a.pushed = r.sent; if (r.errors.length) a.pushErrors = r.errors; pushed.push(a.key);
  }
  if (out.length) {
    const log = await getJSON('alerts', []);
    await setJSON('alerts', [...out.filter(a => !a.silent), ...log].slice(0, 200));
  }
  state.lastRun = new Date(now).toISOString();
  await setJSON('state', state);
  return { ranAt: state.lastRun, marketOpen: open, nifty: nifty?.price, vix: vix?.price, position: pos ? pos.last : null, alerts: out, pushed };
}
