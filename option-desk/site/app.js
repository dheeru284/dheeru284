/* NIFTY Option Desk — app logic. Depends on lib.js (window.ODL) and Chart.js. */
(() => {
  const L = window.ODL;
  const $ = s => document.querySelector(s);
  const el = (tag, attrs = {}, html = '') => Object.assign(document.createElement(tag), attrs, html ? { innerHTML: html } : {});
  const LOT = 65;
  const store = {
    get(k, d) { try { const v = localStorage.getItem('od.' + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
    set(k, v) { try { localStorage.setItem('od.' + k, JSON.stringify(v)); } catch { /* private mode */ } },
  };
  const fmt = (v, d = 0) => (v == null || !isFinite(v) ? '—' : Number(v).toLocaleString('en-IN', { maximumFractionDigits: d, minimumFractionDigits: d }));
  const pct = (v, d = 2) => (v == null || !isFinite(v) ? '—' : `${v > 0 ? '+' : ''}${(v * 100).toFixed(d)}%`);
  const rs = v => (v == null || !isFinite(v) ? '—' : `${v < 0 ? '−' : ''}₹${fmt(Math.abs(v))}`);
  const cls = v => (v > 0 ? 'up' : v < 0 ? 'down' : '');
  const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

  const S = { results: null, market: null, live: null, news: null, chain: null, charts: {} };

  // Upcoming scheduled events. RBI/Budget/elections were filtered in the backtest; FOMC is shown as caution.
  // Scheduled events live in events.json (shared with the auto-trader). RBI/Budget/elections were filtered in the backtest; FOMC is shown as caution.
  let DEFAULT_EVENTS = [];
  const events = () => [...DEFAULT_EVENTS, ...store.get('events', [])].sort((a, b) => a.date.localeCompare(b.date));

  // ------------------------------------------------------------------ tabs & theme
  document.querySelectorAll('.tabs button').forEach(b => b.addEventListener('click', () => {
    document.querySelectorAll('.tabs button').forEach(x => x.classList.toggle('active', x === b));
    document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.id === 'tab-' + b.dataset.tab));
    store.set('tab', b.dataset.tab);
    if (b.dataset.tab === 'news' && !S.news) loadNews();
    if (b.dataset.tab === 'auto') refreshAuto();
    redrawCharts();
  }));
  const savedTheme = store.get('theme', null);
  if (savedTheme) document.documentElement.dataset.theme = savedTheme;
  $('#theme').addEventListener('click', () => {
    const dark = document.documentElement.dataset.theme ? document.documentElement.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
    document.documentElement.dataset.theme = dark ? 'light' : 'dark';
    store.set('theme', document.documentElement.dataset.theme);
    redrawCharts(true);
  });

  // ------------------------------------------------------------------ charts
  const chartDefs = {};
  function chart(id, makeCfg) {
    chartDefs[id] = makeCfg;
    draw(id);
  }
  function draw(id) {
    const c = document.getElementById(id);
    if (!c || !window.Chart || !chartDefs[id] || c.offsetParent === null) return;
    S.charts[id]?.destroy();
    const cfg = chartDefs[id]();
    Chart.defaults.color = css('--muted'); Chart.defaults.borderColor = css('--grid');
    Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
    cfg.options = Object.assign({ responsive: true, maintainAspectRatio: false, animation: false,
      plugins: { legend: { display: false } }, interaction: { mode: 'index', intersect: false } }, cfg.options || {});
    S.charts[id] = new Chart(c, cfg);
  }
  function redrawCharts() { setTimeout(() => Object.keys(chartDefs).forEach(draw), 0); }

  // ------------------------------------------------------------------ data loading
  async function getJSON(url) { const r = await fetch(url, { cache: 'no-store' }); if (!r.ok) throw new Error(`${url} → ${r.status}`); return r.json(); }

  async function boot() {
    [S.results, DEFAULT_EVENTS] = await Promise.all([getJSON('results.json'), getJSON('events.json').catch(() => [])]);
    $('#btdate').textContent = S.results.data_through;
    renderBacktest(); renderMacro(); renderAbout(); renderJournal(); initLab();
    try {
      S.market = await getJSON('/api/market');
      S.live = deriveLive(S.market);
    } catch (e) {
      S.live = fallbackLive();
      $('#stamp').innerHTML = `<span class="down">Live data unavailable (${e.message}).</span> Showing the research snapshot of ${S.results.data_through}.`;
    }
    renderToday();
    const tab = store.get('tab', 'today');
    document.querySelector(`.tabs button[data-tab="${tab}"]`)?.click();
  }
  $('#refresh').addEventListener('click', async () => {
    $('#stamp').textContent = 'Refreshing…';
    try { S.market = await getJSON('/api/market?t=' + Date.now()); S.live = deriveLive(S.market); } catch (e) { $('#stamp').textContent = 'Refresh failed: ' + e.message; }
    renderToday(); if (S.news) loadNews(true);
  });

  // ------------------------------------------------------------------ live state
  function fallbackLive() {
    const st = S.results.state;
    return { fallback: true, nifty: st.nifty, vix: st.vix, dma50: st.dma50, dma200: st.dma200, rv20: st.rv20 / 100,
      vixChg5: NaN, chg20: { 'US VIX': st.usvix_chg20 / 100, 'USD/INR': st.usdinr_chg20 / 100, 'Brent crude': st.brent_chg20 / 100, 'US 10Y yield': st.us10y_chg20_bps },
      quotes: {}, gapX: {}, lastSession: st.date, target: null, inSession: false, actualGap: NaN, from52h: st.from_ath };
  }

  function deriveLive(m) {
    const d = m.data, today = L.iso(L.istToday());
    const nifty = d.NIFTY.bars, vix = d.INDIAVIX?.bars || [];
    const lastBar = nifty[nifty.length - 1];
    const nowMin = (() => { const n = new Date(Date.now() + 5.5 * 3600e3); return n.getUTCHours() * 60 + n.getUTCMinutes(); })();
    const todayTrading = L.isTradingDay(new Date(today + 'T00:00:00Z'));
    // Yahoo sometimes appends a bar dated today on weekends/holidays; only a trading day can be "in session"
    const inSession = todayTrading && lastBar[0] === today && nowMin >= 9 * 60 + 15 && nowMin < 15 * 60 + 30;
    // last completed session and the session being forecast
    const completed = inSession ? nifty.slice(0, -1) : nifty;
    const lastSession = completed[completed.length - 1][0];
    let target = inSession ? today : null;
    if (!target) { let x = L.addDays(new Date(lastSession + 'T00:00:00Z'), 1); while (!L.isTradingDay(x)) x = L.addDays(x, 1); target = L.iso(x); }
    const futureTarget = target > today || (target === today && !inSession && nowMin < 9 * 60 + 15 && todayTrading);
    const closes = completed.map(b => b[4]);
    const sma = n => closes.slice(-n).reduce((a, b) => a + b, 0) / Math.min(n, closes.length);
    const rets = closes.slice(-21).map((c, i, a) => (i ? Math.log(c / a[i - 1]) : null)).filter(v => v != null);
    const mean = rets.reduce((a, b) => a + b, 0) / rets.length;
    const rv20 = Math.sqrt(rets.reduce((a, b) => a + (b - mean) ** 2, 0) / (rets.length - 1) * 252);
    const vixNow = d.INDIAVIX?.price ?? vix[vix.length - 1]?.[4];
    const vixCloses = vix.map(b => b[4]);
    const vixChg5 = vixCloses.length > 6 ? vixNow / vixCloses[vixCloses.length - 6] - 1 : NaN;

    const gapX = {}, chg20 = {}, quotes = {};
    const yields = new Set(['US 10Y yield', 'US 3M T-bill']);
    for (const [name, s] of Object.entries(d)) {
      const bars = s.bars; if (!bars?.length) continue;
      const last = bars[bars.length - 1], prev = bars[bars.length - 2];
      const price = s.price ?? last[4];
      // day change: vs the bar before the live quote's session
      const prevClose = (!s.marketDate || s.marketDate === last[0]) ? prev?.[4] : last[4];
      quotes[name] = { price, chg: yields.has(name) ? (price - prevClose) * 100 : price / prevClose - 1, date: last[0], time: s.time };
      const before = dt => { for (let i = bars.length - 1; i >= 0; i--) if (bars[i][0] < dt) return bars[i][4]; return NaN; };
      const nowV = futureTarget ? price : before(target);
      const base = before(lastSession);
      gapX[name] = yields.has(name) ? (nowV - base) * 100 : nowV / base - 1;
      const c20 = bars.length > 21 ? bars[bars.length - 21][4] : NaN;
      chg20[name] = yields.has(name) ? (price - c20) * 100 : price / c20 - 1;
    }
    const hi52 = Math.max(...closes.slice(-252));
    const actualGap = inSession ? lastBar[1] / completed[completed.length - 1][4] - 1 : NaN;
    return { nifty: d.NIFTY.price ?? lastBar[4], niftyClose: closes[closes.length - 1], vix: vixNow, vixChg5, dma50: sma(50), dma200: sma(200), rv20,
      quotes, gapX, chg20, lastSession, target, inSession, futureTarget, actualGap, from52h: (d.NIFTY.price ?? lastBar[4]) / hi52 - 1,
      fetched: m.fetched, errors: m.errors };
  }

  // ------------------------------------------------------------------ TODAY
  function renderToday() {
    const v = S.live, R = S.results;
    if (!v.fallback) {
      const t = new Date(v.fetched);
      $('#stamp').textContent = `Live (Yahoo, delayed) · fetched ${t.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', hour12: false, dateStyle: 'medium', timeStyle: 'short' })} IST · last NIFTY session ${v.lastSession}${v.inSession ? ' · market open' : ''}`;
    }
    // snapshot
    const show = [['NIFTY', 'NIFTY'], ['BANKNIFTY', 'Bank Nifty'], ['INDIAVIX', 'India VIX'], ['USD/INR', 'USD/INR'], ['Brent crude', 'Brent $'],
      ['Gold', 'Gold $'], ['US 10Y yield', 'US 10Y %'], ['Dollar index (DXY)', 'DXY'], ['S&P 500', 'S&P 500'], ['Nasdaq', 'Nasdaq'],
      ['US VIX', 'US VIX'], ['Nikkei', 'Nikkei'], ['Hang Seng', 'Hang Seng'], ['Bitcoin', 'Bitcoin $']];
    const snap = $('#snapshot'); snap.innerHTML = '';
    if (v.fallback) {
      const st = R.state;
      [['NIFTY', st.nifty], ['India VIX', st.vix], ['USD/INR', st.usdinr], ['Brent $', st.brent], ['Gold $', st.gold], ['US 10Y %', st.us10y], ['DXY', st.dxy]]
        .forEach(([k, x]) => snap.append(el('div', { className: 'card' }, `<div class="k">${k}</div><div class="v">${fmt(x, 2)}</div><div class="d muted">${st.date}</div>`)));
    } else {
      for (const [k, label] of show) {
        const q = v.quotes[k]; if (!q) continue;
        const isY = k.includes('yield');
        const ch = isY ? `${q.chg > 0 ? '+' : ''}${fmt(q.chg, 1)} bp` : pct(q.chg);
        snap.append(el('div', { className: 'card' }, `<div class="k">${label}</div><div class="v">${fmt(q.price, q.price < 200 ? 2 : 0)}</div><div class="d ${cls(isY || k.includes('VIX') || k === 'USD/INR' ? -q.chg : q.chg)}">${ch}</div>`));
      }
    }
    renderGate(); renderGap(); renderMove(); renderPlan(); renderRegime(); renderEvents(); refreshLive();
  }

  function nextExpiries() { return L.niftyExpiries(L.istToday(), 6); }
  function selectedExpiry() {
    const ex = nextExpiries(); const sel = $('#expiry');
    if (!sel.options.length) { ex.forEach(e => sel.append(el('option', { value: e.date }, `${e.date} ${e.weekday}${e.monthly ? ' · monthly' : ''}${e.moved ? ' · moved (holiday)' : ''}`))); sel.addEventListener('change', () => { renderGate(); renderPlan(); renderMove(); }); }
    if (!sel.value || !sel.dataset.init) {
      sel.dataset.init = 1;
      const today = L.iso(L.istToday());
      const ok = ex.find(e => L.iso(L.nthSessionBefore(new Date(e.date + 'T00:00:00Z'), 4)) >= today);
      sel.value = (ok || ex[0]).date;
    }
    return sel.value;
  }

  function straddleIV(expiry) {
    const p = parseFloat($('#straddle').value);
    if (!(p > 0)) return NaN;
    const T = L.yearsTo(expiry);
    const S0 = S.live.nifty; const K = Math.round(S0 / 50) * 50;
    // solve the straddle price for a single vol
    let lo = 0.01, hi = 2;
    for (let i = 0; i < 60; i++) { const m = (lo + hi) / 2; (L.bs(S0, K, T, m, 'C') + L.bs(S0, K, T, m, 'P')) > p ? hi = m : lo = m; }
    return (lo + hi) / 2;
  }
  $('#straddle').addEventListener('input', () => { store.set('straddle', $('#straddle').value); renderGate(); renderPlan(); renderMove(); });
  $('#straddle').value = store.get('straddle', '');

  function gateChecks() {
    const v = S.live, ex = selectedExpiry();
    const entry = L.nthSessionBefore(new Date(ex + 'T00:00:00Z'), 4);
    const winStart = L.iso(entry) < L.iso(L.istToday()) ? L.iso(L.istToday()) : L.iso(entry);
    const evIn = events().filter(e => e.date >= winStart && e.date <= ex);
    const hardEv = evIn.filter(e => e.kind !== 'FOMC'), softEv = evIn.filter(e => e.kind === 'FOMC');
    const c = [];
    const add = (st, title, why) => c.push({ st, title, why });
    add(hardEv.length ? 'bad' : 'good', hardEv.length ? `Event inside the trade: ${hardEv.map(e => `${e.name} ${e.date}`).join(', ')}` : 'No RBI / Budget / election inside the trade window',
      'Backtest: skipping event weeks cut the worst week from −₹58k to −₹33k per lot.');
    if (softEv.length) add('warn', `FOMC inside the window (${softEv.map(e => e.date).join(', ')})`, 'Not filtered in the backtest; US VIX overnight is NIFTY’s 4th-strongest gap driver. Consider half size.');
    const vx = v.vix;
    add(vx < 22 ? 'good' : vx < 30 ? 'warn' : 'bad', `India VIX ${fmt(vx, 2)} ${vx < 22 ? '< 22' : '≥ 22'}`, 'VIX ≥ 22 weeks were excluded: gap risk outweighs the richer premium.');
    if (isFinite(v.vixChg5)) add(v.vixChg5 <= 0.15 ? 'good' : 'bad', `India VIX ${pct(v.vixChg5, 1)} over 5 sessions`, 'Rule: skip if VIX rose more than 15% in 5 sessions (volatility expanding).');
    const uv = v.chg20['US VIX'];
    add(uv <= 0.25 ? 'good' : 'bad', `US VIX ${pct(uv, 1)} over 20 sessions`, 'Macro guard: skip short-vol if US VIX is up >25% in 20 sessions.');
    const inr = v.chg20['USD/INR'];
    add(inr <= 0.015 ? 'good' : 'bad', `USD/INR ${pct(inr, 2)} over 20 sessions (${inr > 0 ? 'rupee weaker' : 'rupee stronger'})`, 'Macro guard: skip if the rupee fell more than 1.5% in 20 sessions.');
    const y = v.chg20['US 10Y yield'];
    add(y < 40 ? 'good' : 'warn', `US 10Y ${y > 0 ? '+' : ''}${fmt(y, 0)} bp over 20 sessions`, 'Yields +40 bp in a month → NIFTY’s next month averaged −1.3% (up only 39%). Bearish tilt, not a hard stop.');
    const cr = v.chg20['Brent crude'];
    add(cr < 0.15 ? 'good' : 'warn', `Brent ${pct(cr, 1)} over 20 sessions`, 'Crude’s link to NIFTY is now the most negative in 10 years (see Macro tab). An oil spike is a live risk.');
    const ivS = straddleIV(ex);
    if (isFinite(ivS)) {
      const ratio = ivS / v.rv20;
      add(ratio >= 1.15 ? 'good' : ratio >= 1.0 ? 'warn' : 'bad', `Option IV ${fmt(ivS * 100, 1)}% vs realised ${fmt(v.rv20 * 100, 1)}% (×${fmt(ratio, 2)})`,
        'The backtest edge exists only when options are priced above the vol NIFTY actually delivers. Below ×1.0 you are selling insurance too cheap.');
    } else add('na', 'Enter the live ATM straddle to check option richness', `Without it, strikes use VIX × 0.95. If real IV is 0.85× VIX the backtest edge falls to ~₹160/lot/week (≈ breakeven).`);
    return { checks: c, entry: L.iso(entry), expiry: ex, ivS };
  }

  function renderGate() {
    if (!S.live) return;
    const { checks, entry, expiry } = gateChecks();
    const bad = checks.filter(x => x.st === 'bad').length, warn = checks.filter(x => x.st === 'warn').length;
    const vd = $('#verdict');
    let txt, k;
    if (bad) { k = 'bad'; txt = `Stand aside from selling premium for the ${expiry} expiry`; }
    else if (warn > 1) { k = 'warn'; txt = 'Trade allowed at half size — wide condor (1.25σ / 2σ)'; }
    else { k = 'good'; txt = 'Gate green — iron condor 1σ / 1.75σ allowed at normal size'; }
    S.verdict = { k, txt };
    vd.className = 'verdict ' + k;
    vd.innerHTML = `${txt}<small>Backtest timing: enter at the close of ${entry} (4 sessions before expiry), hold to the ${expiry} expiry. ${bad ? 'In the backtest, weeks like this were skipped; that filter cut max drawdown from ₹1.08 lakh to ₹52k per lot.' : ''}</small>`;
    const ul = $('#checks'); ul.innerHTML = '';
    checks.forEach(x => ul.append(el('li', {}, `<span class="dot ${x.st}"></span><div>${x.title}<div class="why">${x.why}</div></div>`)));
    $('#vrpnote').textContent = 'Straddle = ATM call + ATM put premium for the selected expiry.';
  }

  function renderGap() {
    const v = S.live, gm = S.results.gap_model, box = $('#gap');
    if (v.fallback) { box.innerHTML = '<p class="muted">Needs live data.</p>'; return; }
    let g = gm.intercept; const rows = [];
    for (const f of gm.factors) {
      const x = v.gapX[f];
      if (!isFinite(x)) continue;
      const xc = Math.min(gm.clip_hi[f], Math.max(gm.clip_lo[f], x));
      const contrib = gm.coef[f] * xc; g += contrib;
      rows.push([f, x, contrib]);
    }
    rows.sort((a, b) => Math.abs(b[2]) - Math.abs(a[2]));
    const pts = g * v.niftyClose;
    const label = v.inSession ? `today (${v.target})` : `next session (${v.target})`;
    box.innerHTML = `<div class="kv">
      <div><span>Model gap ${label}</span><b class="${cls(g)}">${pct(g)} (${pts > 0 ? '+' : ''}${fmt(pts)} pts)</b></div>
      ${v.inSession ? `<div><span>Actual gap today</span><b class="${cls(v.actualGap)}">${pct(v.actualGap)}</b></div>` : ''}
      <div><span>Out-of-sample direction hit</span><b>${fmt(gm.oos_direction_hit * 100, 0)}%</b></div>
      <div><span>…on its strongest 20% calls</span><b>${fmt(gm.oos_direction_hit_top20 * 100, 0)}%</b></div></div>
      <table class="tbl"><thead><tr><th>Overnight driver</th><th>Change</th><th>Contribution</th></tr></thead><tbody>
      ${rows.map(([f, x, c]) => `<tr><td>${f}</td><td>${f.includes('yield') ? `${fmt(x, 1)} bp` : pct(x)}</td><td class="${cls(c)}">${pct(c, 2)}</td></tr>`).join('')}
      </tbody></table>
      <p class="muted small">OLS on ${gm.factors.length} overnight factors, trained 2011–2019, tested ${gm.oos_period} (R² ${fmt(gm.oos_r2, 2)}). The gap tends to fade: after a >1% gap-up, NIFTY averaged ${fmt(S.results.gap_follow['gap up > 1%'].avg_intraday, 2)}% intraday. GIFT Nifty, once trading, beats this model.</p>`;
  }

  function renderMove() {
    const v = S.live, ex = selectedExpiry();
    const T = L.yearsTo(ex), days = T * 365;
    const ivS = straddleIV(ex);
    const sig = v.vix / 100;
    const row = (lab, s) => `<div><span>${lab}</span><b>±${fmt(v.nifty * s)} pts</b><span>${fmt(v.nifty * (1 - s))} – ${fmt(v.nifty * (1 + s))}</span></div>`;
    $('#move').innerHTML = `<div class="kv">
      ${row('1 day (VIX)', sig * Math.sqrt(1 / 365))}
      ${row(`to ${ex} (VIX, ${fmt(days, 1)} d)`, sig * Math.sqrt(T))}
      ${isFinite(ivS) ? row('to expiry (your straddle)', ivS * Math.sqrt(T)) : ''}
      </div><p class="muted small">1σ ≈ 68% of the time in theory. Historically NIFTY stayed inside the VIX 1-week 1σ band ${fmt(S.results.vix_regimes.reduce((a, b) => a + b.stayed_inside_1s * b.days, 0) / S.results.vix_regimes.reduce((a, b) => a + b.days, 0) * 100, 0)}% of weeks: VIX usually overstates the move, and that gap is the option seller’s edge.</p>`;
  }

  function buildLegs(structure, Sx, atm, T) {
    const sT = atm * Math.sqrt(T), r50 = k => Math.round(k / 50) * 50;
    const v = S.live;
    const up = v.nifty > v.dma50;
    let legs;
    if (structure === 'trend') {
      legs = up ? [['SELL', 'P', r50(Sx * Math.exp(-0.8 * sT))], ['BUY', 'P', r50(Sx * Math.exp(-1.5 * sT))]]
        : [['SELL', 'C', r50(Sx * Math.exp(0.8 * sT))], ['BUY', 'C', r50(Sx * Math.exp(1.5 * sT))]];
    } else {
      const [a, b] = structure === 'wide' ? [1.25, 2] : [1, 1.75];
      legs = [['SELL', 'P', r50(Sx * Math.exp(-a * sT))], ['BUY', 'P', r50(Sx * Math.exp(-b * sT))],
        ['SELL', 'C', r50(Sx * Math.exp(a * sT))], ['BUY', 'C', r50(Sx * Math.exp(b * sT))]];
    }
    return legs.map(([side, type, strike]) => ({ side, type, strike, lots: 1, premium: +L.bs(Sx, strike, T, L.skewIV(strike, Sx, atm, T), type).toFixed(2) }));
  }

  // ---- trade card: entry, target, stop-loss (exit rules chosen by the 2011-18 backtest, checked on 2019-26)
  function exitRule(structure) {
    const be = S.results.best_exit?.[structure === 'wide' ? 'wide' : 'ic'];
    return be ? { stop: typeof be.chosen.stop === 'number' ? be.chosen.stop : 1, chosen: be.chosen, hold: be.hold_to_expiry } : { stop: 1 };
  }
  function lossAt(legs, Sx, T, atm) {
    return -legs.reduce((a, l) => a + (l.side === 'BUY' ? 1 : -1) * (L.bs(Sx, l.strike, T, L.skewIV(l.strike, Sx, atm, T), l.type) - l.premium), 0) * LOT;
  }
  function stopSpot(legs, S0, T, atm, lossRs, dir) {
    let lo = S0, hi = S0 * (1 + dir * 0.15);
    if (lossAt(legs, hi, T, atm) < lossRs) return NaN;
    for (let i = 0; i < 60; i++) { const m = (lo + hi) / 2; lossAt(legs, m, T, atm) >= lossRs ? hi = m : lo = m; }
    return (lo + hi) / 2;
  }
  function tradeCard(structure, legs, v, atm, T, ex, st, ch) {
    const rule = exitRule(structure);
    const creditU = st.credit / LOT;
    const minLegs = buildLegs(structure, v.nifty, atm * 0.90 / 0.95, T);
    const minCredit = minLegs.reduce((a, l) => a + (l.side === 'SELL' ? 1 : -1) * l.premium, 0);
    const stopRs = rule.stop * st.credit;
    const buyBack = creditU * (1 + rule.stop);
    const Tmid = Math.max(T - 2 / 365, T / 2);
    const dn = stopSpot(legs, v.nifty, Tmid, atm, stopRs, -1), up = stopSpot(legs, v.nifty, Tmid, atm, stopRs, 1);
    const shorts = legs.filter(l => l.side === 'SELL');
    const c = rule.chosen, h = rule.hold;
    S.card = { stopMult: rule.stop, minCredit };
    return `<h3>Trade card</h3><table class="tbl info"><tbody>
      <tr><td>Entry</td><td>Sell the ${structure === 'trend' ? 'spread' : 'condor'} as one basket (buy wings first) around the close of ${L.iso(L.nthSessionBefore(new Date(ex + 'T00:00:00Z'), 4))}.
        Net credit ≥ <b>₹${fmt(minCredit, 1)}</b> per unit (model ₹${fmt(creditU, 1)}). Below that, options are too cheap: skip the week.</td></tr>
      <tr><td>Target</td><td><b>Hold to expiry</b> and keep up to ${rs(st.credit - ch.total)} per lot if NIFTY settles between ${shorts.map(l => fmt(l.strike)).join(' and ')}.
        Booking early at 50% of the credit cut the backtest's average profit by about 40%, so no early target.</td></tr>
      <tr><td>Stop-loss</td><td>Exit all legs when buying the position back costs <b>₹${fmt(buyBack, 1)}</b> per unit (${fmt(1 + rule.stop, 1)}× the credit), a loss of <b>${rs(stopRs)}</b> per lot.
        At current VIX that is around NIFTY <b>${isFinite(dn) ? fmt(dn) : '—'}</b> / <b>${isFinite(up) ? fmt(up) : '—'}</b>. The backtested rule acts at the close (3:10–3:25 PM); the live monitor tells you to exit at once if the loss reaches 1.5× the stop.</td></tr>
      ${c ? `<tr><td>Why these exits</td><td>Chosen on 2011–18 data only, then checked on 2019–26: stop at ${fmt(rule.stop, 1)}× credit averaged ${rs(c.avg_rs)}/week (2019–26: ${rs(c.avg_2019_26)}), worst run ${rs(c.max_dd_rs)}, vs holding with no stop ${rs(h.avg_rs)} and ${rs(h.max_dd_rs)}. Stops triggered in ${fmt(c.pct_stop * 100, 0)}% of weeks.</td></tr>` : ''}
      ${structure === 'trend' ? '<tr><td>Note</td><td>Exit rules were tested on iron condors; for the trend spread they are applied by analogy.</td></tr>' : ''}
      </tbody></table>`;
  }

  // ---- live alerts (server-side monitor via /api/position and /api/alerts)
  const deskKey = () => store.get('deskkey', '');
  async function api(path, opts = {}) {
    const r = await fetch(path, { ...opts, headers: { 'content-type': 'application/json', 'x-desk-key': deskKey(), ...(opts.headers || {}) } });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.error || `${path} → ${r.status}`);
    return j;
  }
  async function activateTrade() {
    const p = S.plan; if (!p) return;
    const modelU = p.credit / LOT;
    const got = prompt(`Net credit you actually received per unit (sells − buys).\nModel: ₹${modelU.toFixed(2)}. Minimum acceptable: ₹${S.card.minCredit.toFixed(2)}`, modelU.toFixed(2));
    if (got == null) return;
    const actual = parseFloat(got); if (!(actual > 0)) return alert('Enter the credit as a number.');
    if (actual < S.card.minCredit && !confirm(`₹${actual} is below the minimum credit ₹${S.card.minCredit.toFixed(2)}. The backtest edge mostly disappears. Monitor it anyway?`)) return;
    const lots = parseInt(prompt('Lots traded', Math.max(1, p.lots || 1)), 10) || 1;
    const scale = actual / modelU;      // spread the real credit across legs in proportion to the model
    const legs = p.legs.map(l => ({ ...l, lots, premium: +(l.premium * scale).toFixed(2) }));
    try {
      await api('/api/position', { method: 'POST', body: JSON.stringify({ legs, expiry: p.expiry, structure: p.structure, credit: actual * LOT * lots, lots,
        stopMult: S.card.stopMult, spotAtEntry: p.spot, vixAtEntry: p.vix }) });
      const j = J(); j.unshift({ id: Date.now(), logged: new Date().toISOString().slice(0, 10), expiry: p.expiry, structure: p.structure, verdict: S.verdict?.k, taken: true,
        spot: Math.round(p.spot), vix: +p.vix.toFixed(2), legs, credit: Math.round(actual * LOT), settle: null, pnl: null });
      store.set('journal', j); renderJournal();
      refreshLive();
    } catch (e) { alert('Could not start monitoring: ' + e.message); }
  }
  const LEVEL_CLS = { EXIT: 'bad', STOP: 'bad', WARN: 'warn', TARGET: 'good', INFO: 'na', TEST: 'na' };
  let lastAlertTs = store.get('lastAlertTs', '');
  async function refreshLive() {
    const box = $('#live');
    let pos = null, al = null, err = '';
    try { [{ position: pos }, al] = await Promise.all([api('/api/position'), api('/api/alerts')]); } catch (e) { err = e.message; }
    const ch = al?.channels || {};
    let posHtml = '<p class="muted">No position being monitored. After you place a trade, press <b>“I took this trade”</b> in the plan above.</p>';
    if (pos) {
      const stopRs = pos.stopMult * pos.credit;
      posHtml = `<div class="kv">
        <div><span>Position (${pos.expiry})</span><b style="font-size:13px">${pos.legs.map(l => `${l.side === 'SELL' ? 'S' : 'B'} ${l.strike}${l.type === 'C' ? 'CE' : 'PE'}`).join(' · ')}</b><span>${pos.lots} lot(s)</span></div>
        <div><span>Credit received</span><b>${rs(pos.credit)}</b></div>
        <div><span>Stop (loss)</span><b class="down">${rs(-stopRs)}</b><span>hard exit at ${rs(-1.5 * stopRs)}</span></div>
        <div><span>Last check</span><b class="${cls(pos.last?.pnl)}">${pos.last ? rs(pos.last.pnl) : '—'}</b><span>${pos.last ? `NIFTY ${fmt(pos.last.spot)} · ${new Date(pos.last.ts).toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour12: false })}` : 'waiting for market hours'}</span></div>
        </div><button class="btn ghost" id="closepos">I closed this trade: stop alerts</button>`;
    }
    const alerts = al?.alerts || [];
    box.innerHTML = `
      ${err ? `<p class="down">${err === 'wrong or missing desk key' ? 'Enter your desk key to connect.' : 'Live monitor unavailable: ' + err}</p>` : ''}
      <div class="row wrap">
        <label>Desk key <input id="deskkey" type="password" value="${deskKey()}" placeholder="from your setup message"></label>
        <button class="btn ghost" id="testpush">Send test alert</button>
        <button class="btn ghost" id="runnow">Run check now</button>
        <button class="btn ghost" id="browsernotif">${typeof Notification !== 'undefined' && Notification.permission === 'granted' ? 'Browser alerts on ✓' : 'Enable browser alerts'}</button>
      </div>
      <p class="muted small">Phone push: ntfy ${ch.ntfy ? '✓' : '✗'} · Telegram ${ch.telegram ? '✓' : '✗'} · last server check ${al?.lastRun ? new Date(al.lastRun).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', hour12: false, dateStyle: 'medium', timeStyle: 'short' }) + ' IST' : '—'}.
        Prices come from Yahoo and can lag the exchange by a few minutes; for true tick data connect a broker API.</p>
      ${posHtml}
      <h3>Alerts</h3>
      <ul class="checks">${alerts.slice(0, 25).map(a => `<li><span class="dot ${LEVEL_CLS[a.level] || 'na'}"></span><div><b>${a.level}</b> · ${a.title.replace(/</g, '&lt;')}
        <div class="why">${new Date(a.ts).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', hour12: false, dateStyle: 'medium', timeStyle: 'short' })} · ${(a.body || '').replace(/</g, '&lt;').replace(/\n(https?:\/\/\S+)/, ' · <a href="$1" target="_blank" rel="noopener">source</a>')}</div></div></li>`).join('') || '<li class="muted">No alerts yet.</li>'}</ul>`;
    $('#deskkey').onchange = e => { store.set('deskkey', e.target.value.trim()); refreshLive(); };
    $('#testpush').onclick = async () => { try { const r = await api('/api/alerts', { method: 'POST', body: '{"action":"test"}' }); alert(r.sent.length ? `Sent via ${r.sent.join(', ')}` : `Not sent: ${r.errors.join('; ')}`); } catch (e) { alert(e.message); } };
    $('#runnow').onclick = async () => { try { const r = await api('/api/alerts', { method: 'POST', body: '{"action":"run"}' }); alert(`Checked. NIFTY ${fmt(r.nifty)}, ${r.alerts.length} new alert(s).`); refreshLive(); } catch (e) { alert(e.message); } };
    $('#browsernotif').onclick = async () => { if (typeof Notification !== 'undefined') { await Notification.requestPermission(); refreshLive(); } };
    if ($('#closepos')) $('#closepos').onclick = async () => { if (confirm('Stop monitoring this position?')) { await api('/api/position', { method: 'DELETE' }); refreshLive(); } };
    // browser notification for new urgent alerts while the page is open
    const fresh = alerts.filter(a => a.ts > lastAlertTs && ['EXIT', 'WARN', 'TARGET'].includes(a.level));
    if (lastAlertTs && fresh.length && typeof Notification !== 'undefined' && Notification.permission === 'granted')
      fresh.slice(0, 3).forEach(a => new Notification(`${a.level}: ${a.title}`, { body: a.body || '', tag: a.key }));
    if (alerts[0]) { lastAlertTs = alerts[0].ts; store.set('lastAlertTs', lastAlertTs); }
  }
  setInterval(() => { if (!document.hidden) refreshLive(); }, 60000);

  // ---- Auto-trader tab (reads what trader/trader.mjs on your server publishes)
  const AUTO_CLS = { TRADE: 'good', TARGET: 'good', EXIT: 'bad', ERROR: 'bad', STOP: 'bad', WARN: 'warn', INFO: 'na' };
  const istTime = iso => new Date(iso).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', hour12: false, dateStyle: 'medium', timeStyle: 'short' });
  async function refreshAuto() {
    let d;
    try { d = await api('/api/auto'); }
    catch (e) { $('#autostatus').innerHTML = `<p class="down">${e.message === 'wrong or missing desk key' ? 'Enter your desk key on the Today tab (Live exit alerts) first.' : e.message}</p>`; return; }
    const st = d.status, c = d.control, sm = d.summary;
    const mode = (st?.mode || 'not connected').toUpperCase();
    $('#automode').textContent = mode; $('#automode').style.background = mode === 'LIVE' ? 'var(--bad-bg)' : 'var(--chip)';
    $('#autoonline').textContent = d.online ? 'online' : st ? 'offline' : 'waiting for server';
    $('#autoonline').className = 'chip ' + (d.online ? 'up' : 'down');
    const nx = st?.nextEntry, ld = st?.lastDecision;
    if (!st) {
      $('#autostatus').innerHTML = `<div class="note"><b>Why “not connected”?</b> The auto-trader is a separate program that must run on a server with a fixed (static) IP address — SEBI requires API orders to come from an IP registered with Angel One, and this website has no fixed IP. Until that program is running, nothing can be traded and this tab stays empty.
        <ol style="margin:8px 0 0 18px;padding:0">
          <li>Create a free server with a static IP (Oracle Cloud Always Free, Mumbai) or a ₹400/month AWS Lightsail one.</li>
          <li>Create a SmartAPI app at smartapi.angelbroking.com, get the API key, register the server’s IP.</li>
          <li>Enable TOTP on your Angel login and keep the text secret.</li>
          <li>Install the trader on the server, fill in <code>trader/.env</code> on the server (MODE=paper), run <code>node trader/trader.mjs --check</code>.</li>
          <li>Start it as a service. This tab turns <b>online</b> within a minute.</li>
        </ol>Full steps: <code>option-desk/trader/README.md</code>.</div>`;
    }
    if (st) $('#autostatus').innerHTML = `<table class="tbl info"><tbody>
      <tr><td>Auto-trading</td><td><b class="${c.enabled ? 'up' : 'down'}">${c.enabled ? 'ENABLED' : 'PAUSED'}</b>${c.disabledReason ? ` · ${c.disabledReason}` : ''}${c.flatten ? ' · exit requested, executing on next cycle' : ''}</td></tr>
      <tr><td>Server heartbeat</td><td>${st?.beat ? istTime(st.beat) + ' IST' : 'never: the trader is not running yet (see trader/README.md)'}</td></tr>
      <tr><td>Next entry</td><td>${nx ? `${nx.entryDay} 15:10–15:24 IST for the ${nx.expiry} expiry` : '—'}</td></tr>
      <tr><td>Last decision</td><td>${ld ? `${ld.date}: gate <b>${ld.verdict}</b> · ${ld.checks.filter(x => x.st !== 'good').map(x => x.title).join('; ') || 'all green'}` : '—'}</td></tr>
      <tr><td>Limits</td><td>${st?.limits ? `max ${st.limits.lotsMax} lot(s) · risk ${st.limits.riskPct}% of ₹${fmt(st.limits.capital)} · stop ${st.limits.stopMult}× credit at close · hard exit ${st.limits.hardMult}× · monthly loss limit ₹${fmt(st.limits.maxMonthlyLoss)}${st.limits.target ? ` · target ${st.limits.target * 100}% of credit` : ' · target: hold to expiry'}` : '—'}</td></tr>
      </tbody></table>`;
    $('#autosummary').innerHTML = `<div class="kv">
      <div><span>Total P&L</span><b class="${cls(sm.total)}">${rs(sm.total)}</b></div>
      <div><span>This month</span><b class="${cls(sm.month)}">${rs(sm.month)}</b></div>
      <div><span>Last 7 days</span><b class="${cls(sm.week)}">${rs(sm.week)}</b></div>
      <div><span>Open position</span><b class="${cls(sm.open)}">${d.position ? rs(sm.open) : '—'}</b></div>
      <div><span>Trades / wins</span><b>${sm.trades} / ${sm.wins}</b><span>${sm.trades ? fmt(sm.wins / sm.trades * 100, 0) + '% win rate' : ''}</span></div>
      <div><span>Best / worst</span><b>${rs(sm.best)} / ${rs(sm.worst)}</b></div></div>`;
    const p = d.position;
    $('#autopos').innerHTML = p ? `<table class="tbl"><thead><tr><th>Leg</th><th>Qty</th><th>Entry</th><th>Now</th><th>P&L</th></tr></thead><tbody>
      ${p.legs.map(l => { const pl = l.mark != null ? (l.side === 'SELL' ? l.premium - l.mark : l.mark - l.premium) * l.qty : null;
        return `<tr><td>${l.side} ${l.strike} ${l.type === 'C' ? 'CE' : 'PE'}</td><td>${l.qty}</td><td>₹${fmt(l.premium, 2)}</td><td>${l.mark != null ? '₹' + fmt(l.mark, 2) : '—'}</td><td class="${cls(pl)}">${pl != null ? rs(pl) : '—'}</td></tr>`; }).join('')}
      </tbody></table><div class="kv">
      <div><span>Expiry</span><b>${p.expiry}</b><span>${p.structure === 'ic' ? 'iron condor' : 'wide condor'} · ${p.lots} lot(s)</span></div>
      <div><span>Credit</span><b>${rs(p.credit)}</b></div>
      <div><span>P&L now</span><b class="${cls(p.last?.pnl)}">${p.last ? rs(p.last.pnl) : '—'}</b><span>${p.last ? `NIFTY ${fmt(p.last.spot)} · ${istTime(p.last.ts)}` : ''}</span></div>
      <div><span>Stop at close / hard exit</span><b class="down">${rs(-p.stopMult * p.credit)} / ${rs(-p.hardMult * p.stopMult * p.credit)}</b></div></div>
      ${p.exitError ? `<p class="verdict bad">Exit failed: ${p.exitError}. Close the position in Angel One.</p>` : ''}` : '<p class="muted">No open position.</p>';
    const tr = [...d.trades].reverse(); let cum = 0;
    const eq = tr.map(t => [istDate(t.closed), cum += t.pnl]);
    chart('autoeq', () => ({ type: 'line', data: { labels: eq.map(e => e[0]), datasets: [{ data: eq.map(e => e[1]), borderColor: css('--c1'), pointRadius: 2, borderWidth: 1.6 }] },
      options: { scales: { y: { title: { display: true, text: '₹' } } } } }));
    $('#autotrades').innerHTML = d.trades.length ? `<table class="tbl"><thead><tr><th>Closed</th><th>Mode</th><th>Expiry</th><th>Legs (entry → exit)</th><th>Lots</th><th>Credit</th><th>Reason</th><th>Charges</th><th>Net P&L</th></tr></thead><tbody>
      ${d.trades.map(t => `<tr><td>${istTime(t.closed)}</td><td>${(t.mode || '').toUpperCase()}</td><td>${t.expiry}</td><td>${(t.legs || []).map(l => `${l.leg} ${l.entry}→${l.exit}`).join('<br>')}</td><td>${t.lots}</td><td>${rs(t.credit)}</td><td>${t.reason}</td><td>${rs(t.charges)}</td><td class="${cls(t.pnl)}"><b>${rs(t.pnl)}</b></td></tr>`).join('')}</tbody></table>` : '<p class="muted">No closed trades yet.</p>';
    $('#autolog').innerHTML = d.log.map(e => `<li><span class="dot ${AUTO_CLS[e.level] || 'na'}"></span><div><b>${e.level}</b> · ${e.title.replace(/</g, '&lt;')}<div class="why">${istTime(e.ts)} · ${(e.body || '').replace(/</g, '&lt;')}</div></div></li>`).join('') || '<li class="muted">No activity yet.</li>';
  }
  const istDate = iso => new Date(Date.parse(iso) + 5.5 * 3600e3).toISOString().slice(0, 10);
  const autoAction = async (action, ask) => { if (ask && !confirm(ask)) return; try { await api('/api/auto', { method: 'POST', body: JSON.stringify({ action }) }); refreshAuto(); } catch (e) { alert(e.message); } };
  $('#autoenable').onclick = () => autoAction('enable', 'Enable automatic trading? In LIVE mode the server will place real orders in your Angel One account on the next entry day.');
  $('#autopause').onclick = () => autoAction('pause');
  $('#autoflatten').onclick = () => autoAction('flatten', 'Close the open position at market prices and pause auto-trading?');
  setInterval(() => { if (!document.hidden && $('#tab-auto').classList.contains('active')) refreshAuto(); }, 30000);

  const BT_NAME = { ic: 'Iron condor + macro guard', wide: 'Wide iron condor 1.25σ/2σ + macro guard', trend: 'Trend credit spread + macro guard' };
  function renderPlan() {
    if (!S.live) return;
    const v = S.live, ex = selectedExpiry(), structure = $('#structure').value;
    const T = L.yearsTo(ex);
    const ivS = straddleIV(ex);
    const atm = isFinite(ivS) ? ivS : v.vix / 100 * 0.95;
    const legs = buildLegs(structure, v.nifty, atm, T);
    const st = L.strategyStats(legs, v.nifty, atm, T, LOT);
    const ch = L.charges(legs, LOT);
    const maxLoss = -st.maxL + ch.total;
    const cap = +$('#capital').value || 0, rp = (+$('#riskpct').value || 0) / 100;
    const lots = Math.floor(cap * rp / maxLoss);
    const bt = S.results.backtests.find(b => b.name === BT_NAME[structure]);
    S.plan = { legs, expiry: ex, structure, atm, spot: v.nifty, vix: v.vix, credit: st.credit, maxLoss, lots };
    $('#plan').innerHTML = `
      <table class="tbl"><thead><tr><th>Leg</th><th>Strike</th><th>Model premium</th><th>Distance</th></tr></thead><tbody>
      ${legs.map(l => `<tr><td>${l.side} ${l.type === 'C' ? 'CE' : 'PE'}</td><td>${fmt(l.strike)}</td><td>₹${fmt(l.premium, 2)}</td><td>${pct(l.strike / v.nifty - 1, 1)}</td></tr>`).join('')}
      </tbody></table>
      <div class="kv">
        <div><span>Credit / lot (model)</span><b>${rs(st.credit)}</b></div>
        <div><span>Max loss / lot incl. charges</span><b class="down">${rs(maxLoss)}</b></div>
        <div><span>Breakevens</span><b>${st.be.map(x => fmt(x)).join(' / ')}</b></div>
        <div><span>Probability of profit</span><b>${fmt(st.pop * 100, 0)}%</b></div>
        <div><span>Lots at ${fmt(rp * 100, 1)}% risk</span><b>${lots > 0 ? lots : 0}</b><span>1 lot needs ₹${fmt(maxLoss / rp)} capital at this risk</span></div>
        <div><span>Charges / lot</span><b>${rs(ch.total)}</b></div>
      </div>
      ${tradeCard(structure, legs, v, atm, T, ex, st, ch)}
      ${bt ? `<p class="note">Backtest of this structure (with macro guard, ${bt.trades} weeks): win rate ${fmt(bt.win_rate * 100, 0)}%, average ${rs(bt.avg_pnl_rs)}/lot/week, average loss ${rs(bt.avg_loss_rs)}, worst week ${rs(bt.worst_rs)}, max drawdown ${rs(bt.max_dd_rs)}. Last 52 trades: average ${rs(bt.last_52_trades.avg)}.</p>` : ''}
      <p class="muted small">Premiums are Black-Scholes estimates (${isFinite(ivS) ? 'from your straddle' : 'India VIX × 0.95'}, backtest skew). Use real bid/ask from your broker; if the real credit is much lower than the model, the edge is gone. Place as a basket (buy wings first) for the hedge margin benefit. Exit early on a close beyond a short strike or at 2× the credit lost.</p>
      <div class="row wrap"><button class="btn" id="activate">I took this trade: start live alerts</button><button class="btn ghost" id="tolab">Open in Strategy lab →</button></div>`;
    $('#activate').onclick = () => activateTrade();
    $('#tolab').onclick = () => { setLab(legs, v.nifty, atm * 100, ex); document.querySelector('.tabs button[data-tab="lab"]').click(); };
  }
  ['#structure', '#capital', '#riskpct'].forEach(s => $(s).addEventListener('input', () => { store.set(s, $(s).value); renderPlan(); }));
  ['#structure', '#capital', '#riskpct'].forEach(s => { const x = store.get(s, null); if (x != null) $(s).value = x; });

  function renderRegime() {
    const v = S.live, R = S.results;
    const vb = R.vix_regimes.find(b => { const [a, c] = b.bucket.includes('<') ? [0, +b.bucket.slice(1)] : b.bucket.includes('>') ? [+b.bucket.slice(1), 999] : b.bucket.split('-').map(Number); return v.vix >= a && v.vix < c; });
    const trend = v.nifty > v.dma200 ? (v.dma50 > v.dma200 && v.nifty > v.dma50 ? '50>200 & above 50' : 'Above 200 DMA') : (v.dma50 < v.dma200 && v.nifty < v.dma50 ? '50<200 & below 50' : 'Below 200 DMA');
    const tr = R.trend[trend];
    const st = R.state;
    const hiking = st.repo_chg_6m > 0, cutting = st.repo_chg_6m < 0;
    const cyc = R.cycles[hiking ? 'RBI hiking (6m)' : cutting ? 'RBI cutting (6m)' : 'RBI on hold (6m)'];
    $('#regime').innerHTML = `<table class="tbl info"><tbody>
      <tr><td>Trend</td><td>${trend}: NIFTY ${fmt(v.nifty)} · 50 DMA ${fmt(v.dma50)} · 200 DMA ${fmt(v.dma200)}</td></tr>
      <tr><td>History in this trend</td><td>next month avg ${fmt(tr.mean_fwd21, 2)}%, up ${fmt(tr.up_pct_fwd21 * 100, 0)}% of the time, daily vol ${fmt(tr.daily_vol, 2)}%</td></tr>
      <tr><td>India VIX bucket ${vb?.bucket}</td><td>${vb ? `NIFTY stayed inside the weekly 1σ ${fmt(vb.stayed_inside_1s * 100, 0)}% of weeks; worst week ${fmt(vb.worst_week, 1)}%` : ''}</td></tr>
      <tr><td>Realised vol (20 d)</td><td>${fmt(v.rv20 * 100, 1)}% vs India VIX ${fmt(v.vix, 1)}</td></tr>
      <tr><td>RBI repo ${fmt(st.repo, 2)}%</td><td>${hiking ? 'Hiking cycle (since 7 Oct 2026)' : cutting ? 'Cutting cycle' : 'On hold'}: NIFTY historically ${fmt(cyc.ann_return, 1)}%/yr in this phase</td></tr>
      <tr><td>US rates</td><td>3M T-bill ${fmt(v.quotes['US 3M T-bill']?.price ?? st.us3m, 2)}%, 10Y ${fmt(v.quotes['US 10Y yield']?.price ?? st.us10y, 2)}% (${fmt(v.chg20['US 10Y yield'], 0)} bp / 20 d)</td></tr>
      <tr><td>From 52-week high</td><td>${pct(v.from52h, 1)}</td></tr>
      </tbody></table>`;
  }

  function renderEvents() {
    const ex = nextExpiries();
    const today = L.iso(L.istToday());
    const list = [...events().filter(e => e.date >= today).slice(0, 8), ...ex.map(e => ({ date: e.date, name: `NIFTY ${e.monthly ? 'monthly' : 'weekly'} expiry${e.moved ? ' (moved for holiday)' : ''}`, kind: 'Expiry' }))]
      .sort((a, b) => a.date.localeCompare(b.date)).slice(0, 12);
    $('#events').innerHTML = `<table class="tbl info"><tbody>${list.map(e => `<tr><td>${e.date}</td><td>${e.name} <span class="chip">${e.kind}</span></td></tr>`).join('')}</tbody></table>
      <div class="row wrap"><label>Date <input type="date" id="evdate"></label><label>Event <input id="evname" placeholder="e.g. US CPI"></label>
      <label>Type <select id="evkind"><option>RBI</option><option>FOMC</option><option>Budget</option><option>Election</option><option>Other</option></select></label>
      <button class="btn ghost" id="evadd">Add</button></div>
      <p class="muted small">Holiday calendar verified to ${L.HOLIDAYS_KNOWN_UNTIL}. RBI, Budget and election days inside a trade turn the gate red.</p>`;
    $('#evadd').onclick = () => {
      const date = $('#evdate').value, name = $('#evname').value.trim(); if (!date || !name) return;
      store.set('events', [...store.get('events', []), { date, name, kind: $('#evkind').value }]); renderEvents(); renderGate();
    };
  }

  // ------------------------------------------------------------------ CHAIN
  $('#chainfile').addEventListener('change', async e => {
    const f = e.target.files[0]; if (!f) return;
    try { const rows = L.parseChainCSV(await f.text()); showChain(rows, +$('#chainspot').value || S.live?.nifty, `CSV ${f.name}`); }
    catch (err) { $('#chainout').innerHTML = `<p class="down">${err.message}</p>`; }
  });
  $('#loadnse').addEventListener('click', async () => {
    $('#chainout').innerHTML = '<p class="muted">Asking NSE…</p>';
    try {
      const r = await fetch('/api/chain?symbol=NIFTY'); const j = await r.json();
      if (!j.ok) throw new Error(j.error);
      showChain(j.rows, j.underlying, `NSE ${j.expiry || ''} ${j.timestamp || ''}`);
    } catch (e) { $('#chainout').innerHTML = `<p class="down">${e.message}</p>`; }
  });
  function showChain(rows, spot, src) {
    if (!(spot > 0)) spot = rows[Math.floor(rows.length / 2)].strike;
    $('#chainspot').value = spot;
    const a = L.analyseChain(rows, spot);
    S.chain = { rows, a, spot };
    const pcrRead = a.pcr > 1.5 ? 'crowded bullish (contrarian caution)' : a.pcr > 1 ? 'supportive' : a.pcr < 0.6 ? 'washed out' : a.pcr < 0.7 ? 'call-heavy, bearish lean' : 'neutral';
    $('#chainout').innerHTML = `<p class="muted small">Source: ${src} · ${rows.length} strikes</p><div class="kv">
      <div><span>PCR (OI)</span><b>${fmt(a.pcr, 2)}</b><span>${pcrRead}</span></div>
      <div><span>PCR (change in OI)</span><b>${fmt(a.pcrChange, 2)}</b></div>
      <div><span>Max pain</span><b>${fmt(a.maxPain)}</b></div>
      <div><span>Call wall (resistance)</span><b>${fmt(a.callWall)}</b></div>
      <div><span>Put wall (support)</span><b>${fmt(a.putWall)}</b></div>
      <div><span>Fresh call / put writing</span><b>${fmt(a.freshCall)} / ${fmt(a.freshPut)}</b></div>
      <div><span>ATM ${fmt(a.atm)} straddle</span><b>₹${fmt(a.straddle, 2)}</b><span>±${fmt(a.straddle / spot * 100, 2)}% priced move</span></div>
      <div><span>ATM IV call / put</span><b>${fmt(a.atmCallIV, 1)} / ${fmt(a.atmPutIV, 1)}</b></div>
      <div><span>Skew (3% OTM put − call IV)</span><b>${fmt(a.skew, 1)}</b></div></div>
      <button class="btn ghost" id="usestraddle">Use this straddle in the trade gate</button>`;
    $('#usestraddle').onclick = () => { $('#straddle').value = a.straddle.toFixed(2); store.set('straddle', $('#straddle').value); renderGate(); renderPlan(); renderMove(); document.querySelector('.tabs button[data-tab="today"]').click(); };
    const vis = rows.filter(r => Math.abs(r.strike / spot - 1) < 0.06);
    chart('oichart', () => ({ type: 'bar', data: { labels: vis.map(r => r.strike), datasets: [
      { label: 'Call OI', data: vis.map(r => r.call_oi || 0), backgroundColor: css('--bad') },
      { label: 'Put OI', data: vis.map(r => r.put_oi || 0), backgroundColor: css('--good') }] },
      options: { plugins: { legend: { display: true } } } }));
  }

  // ------------------------------------------------------------------ LAB
  let labLegs = [];
  function initLab() {
    const ex = L.niftyExpiries(L.istToday(), 8);
    ex.forEach(e => $('#labexp').append(el('option', { value: e.date }, `${e.date} ${e.weekday}${e.monthly ? ' · monthly' : ''}`)));
    const st = S.results.state;
    $('#labspot').value = Math.round(st.nifty); $('#labiv').value = (st.vix * 0.95).toFixed(1);
    labLegs = store.get('lablegs', []);
    if (!labLegs.length) labLegs = [{ side: 'SELL', type: 'P', strike: Math.round(st.nifty * 0.98 / 50) * 50, premium: 0, lots: 1 }];
    ['#labspot', '#labiv', '#labexp', '#lablot'].forEach(s => $(s).addEventListener('input', renderLab));
    $('#labadd').onclick = () => { labLegs.push({ side: 'BUY', type: 'C', strike: Math.round(+$('#labspot').value / 50) * 50, premium: 0, lots: 1 }); renderLab(); };
    $('#labprice').onclick = () => {
      const Sx = +$('#labspot').value, atm = +$('#labiv').value / 100, T = L.yearsTo($('#labexp').value);
      labLegs.forEach(l => { l.premium = +L.bs(Sx, l.strike, T, L.skewIV(l.strike, Sx, atm, T), l.type).toFixed(2); }); renderLab();
    };
    renderLab();
  }
  function setLab(legs, spot, iv, ex) {
    labLegs = legs.map(l => ({ ...l })); $('#labspot').value = Math.round(spot); $('#labiv').value = iv.toFixed(1);
    if ([...$('#labexp').options].some(o => o.value === ex)) $('#labexp').value = ex; renderLab();
  }
  function renderLab() {
    store.set('lablegs', labLegs);
    const tb = $('#legs tbody'); tb.innerHTML = '';
    labLegs.forEach((l, i) => {
      const tr = el('tr', {}, `<td><select data-k="side"><option>BUY</option><option>SELL</option></select></td>
        <td><select data-k="type"><option value="C">CE</option><option value="P">PE</option></select></td>
        <td><input data-k="strike" type="number" step="50" value="${l.strike}"></td>
        <td><input data-k="premium" type="number" step="0.05" value="${l.premium}"></td>
        <td><input data-k="lots" type="number" min="1" value="${l.lots}"></td><td><button class="btn ghost" data-del>✕</button></td>`);
      tr.querySelector('[data-k="side"]').value = l.side; tr.querySelector('[data-k="type"]').value = l.type;
      tr.querySelectorAll('[data-k]').forEach(inp => inp.addEventListener('change', () => { const k = inp.dataset.k; l[k] = k === 'side' || k === 'type' ? inp.value : +inp.value; renderLab(); }));
      tr.querySelector('[data-del]').onclick = () => { labLegs.splice(i, 1); renderLab(); };
      tb.append(tr);
    });
    if (!labLegs.length) { $('#labstats').innerHTML = ''; return; }
    const Sx = +$('#labspot').value, sig = +$('#labiv').value / 100, T = L.yearsTo($('#labexp').value), lot = +$('#lablot').value || LOT;
    const st = L.strategyStats(labLegs, Sx, sig, T, lot);
    const ch = L.charges(labLegs, lot);
    $('#labstats').innerHTML = `<div class="kv">
      <div><span>Net ${st.credit >= 0 ? 'credit' : 'debit'}</span><b>${rs(Math.abs(st.credit))}</b></div>
      <div><span>Max profit</span><b class="up">${st.unlimitedUp ? 'Unlimited' : rs(st.maxP)}</b></div>
      <div><span>Max loss</span><b class="down">${st.unlimitedUp || st.unlimitedDown ? 'Unlimited / very large' : rs(st.maxL)}</b></div>
      <div><span>Breakevens</span><b>${st.be.map(x => fmt(x)).join(' / ') || '—'}</b></div>
      <div><span>Probability of profit</span><b>${fmt(st.pop * 100, 0)}%</b></div>
      <div><span>Δ / Θ per day / Vega</span><b>${fmt(st.net.delta, 1)} / ${rs(st.net.theta)} / ${rs(st.net.vega)}</b></div>
      <div><span>Charges (to expiry)</span><b>${rs(ch.total)}</b></div></div>`;
    chart('payoff', () => ({ type: 'line', data: { datasets: [{ data: st.pts.map(([x, y]) => ({ x, y })), borderColor: css('--c1'), pointRadius: 0, borderWidth: 2,
      fill: { target: 'origin', above: css('--good-bg'), below: css('--bad-bg') } }] },
      options: { scales: { x: { type: 'linear', title: { display: true, text: 'NIFTY at expiry' } }, y: { title: { display: true, text: '₹ P&L' } } } } }));
  }

  // ------------------------------------------------------------------ BACKTEST
  function renderBacktest() {
    const B = S.results.backtests;
    $('#btmeta').textContent = `Weekly expiries Jan 2011 – ${S.results.data_through}. Entry at the close 4 sessions before expiry, held to expiry. P&L per 1 lot of ${LOT}, restated at NIFTY ${fmt(S.results.scale_spot)} so early years compare with today. Premiums from Black-Scholes on India VIX × 0.95 with put skew (free historical option-chain data does not exist), minus 0.75 pt slippage per leg, STT, exchange fees, GST, stamp duty and ₹20/leg brokerage.`;
    const best = B.filter(b => b.trades > 100).reduce((a, b) => (b.sharpe_weekly_ann > a.sharpe_weekly_ann ? b : a));
    $('#bttable').innerHTML = `<thead><tr><th>Strategy</th><th>Weeks</th><th>Win %</th><th>Avg ₹/trade</th><th>Avg win</th><th>Avg loss</th><th>Worst</th><th>Max DD</th><th>Profit factor</th><th>Sharpe</th><th>2011–18 avg</th><th>2019–26 avg</th><th>Last 52 avg</th></tr></thead><tbody>
      ${B.map(b => `<tr class="${b === best ? 'hl' : ''}" title="${b.desc}"><td>${b.name}<div class="muted small">${b.desc}</div></td><td>${b.trades}</td><td>${fmt(b.win_rate * 100, 0)}</td>
      <td class="${cls(b.avg_pnl_rs)}">${rs(b.avg_pnl_rs)}</td><td>${rs(b.avg_win_rs)}</td><td>${rs(b.avg_loss_rs)}</td><td class="down">${rs(b.worst_rs)}</td><td class="down">${rs(b.max_dd_rs)}</td>
      <td>${fmt(b.profit_factor, 2)}</td><td>${fmt(b.sharpe_weekly_ann, 2)}</td><td>${rs(b.in_sample_2011_2018.avg)}</td><td>${rs(b.out_of_sample_2019_now.avg)}</td><td class="${cls(b.last_52_trades.avg)}">${rs(b.last_52_trades.avg)}</td></tr>`).join('')}</tbody>`;
    const pick = $('#btpick');
    B.forEach(b => pick.append(el('option', { value: b.name }, b.name)));
    pick.value = best.name;
    const drawBt = () => {
      const b = B.find(x => x.name === pick.value);
      chart('eqchart', () => ({ type: 'line', data: { labels: b.equity.map(e => e[0]), datasets: [{ data: b.equity.map(e => e[1]), borderColor: css('--c1'), pointRadius: 0, borderWidth: 1.6 }] },
        options: { scales: { x: { ticks: { maxTicksLimit: 8 } }, y: { title: { display: true, text: '₹ cumulative, 1 lot' } } } } }));
      const yrs = Object.keys(b.yearly);
      chart('yrchart', () => ({ type: 'bar', data: { labels: yrs, datasets: [{ data: yrs.map(y => b.yearly[y].pnl), backgroundColor: yrs.map(y => (b.yearly[y].pnl >= 0 ? css('--good') : css('--bad'))) }] } }));
    };
    pick.addEventListener('change', drawBt); drawBt();
    const s = S.results.sensitivity;
    $('#sens').innerHTML = `<table class="tbl"><thead><tr><th>Iron condor + macro guard, if…</th><th>Avg ₹/trade</th><th>Win %</th><th>Max DD</th><th>Profit factor</th></tr></thead><tbody>
      ${s.map(x => `<tr><td>${x.atm_iv_vs_vix != null ? `real weekly IV = ${x.atm_iv_vs_vix} × India VIX` : `slippage ${x.slippage_pts_per_leg} pts per leg`}</td><td class="${cls(x.avg_pnl_rs)}">${rs(x.avg_pnl_rs)}</td><td>${fmt(x.win_rate * 100, 0)}</td><td class="down">${rs(x.max_dd_rs)}</td><td>${fmt(x.profit_factor, 2)}</td></tr>`).join('')}</tbody></table>
      <p class="note">Read this before trusting any number above. The edge comes from options being priced above the volatility NIFTY then delivers. If real weekly premiums are cheaper than VIX × 0.95 (common in calm markets) or your fills are poor, the profit mostly disappears while the tail losses stay. That is why the Today tab asks for the live straddle and why the Journal exists.</p>`;
  }

  // ------------------------------------------------------------------ MACRO
  function renderMacro() {
    const R = S.results;
    // trends
    const T = [];
    const rc = R.rolling_corr;
    for (const [k, x] of Object.entries(rc).sort((a, b) => Math.abs(b[1].shift_z) - Math.abs(a[1].shift_z))) {
      if (Math.abs(x.shift_z) < 1.3) continue;
      const extreme = x.corr_1y <= x.corr_10y_min + 0.02 ? ' — the most negative in 10 years' : x.corr_1y >= x.corr_10y_max - 0.02 ? ' — the highest in 10 years' : '';
      T.push([`${k}: link to NIFTY has ${x.shift_z < 0 ? 'turned negative' : 'strengthened'}`,
        `1-year correlation ${fmt(x.corr_1y, 2)} (3-month ${fmt(x.corr_3m, 2)}) vs 10-year average ${fmt(x.corr_10y_avg, 2)}${extreme}. ${k === 'Brent crude' ? 'Oil spikes now hit Indian stocks directly; with Brent near $' + fmt(R.state.brent, 0) + ' this is the macro risk to watch.' : k === 'US 10Y yield' ? 'Rising US yields now pull FII money out of India; a +40 bp month historically preceded −1.3% for NIFTY.' : k === 'Gold' ? 'Gold and NIFTY rising together: a liquidity / weak-dollar trade rather than a fear hedge.' : ''}`]);
    }
    const us = rc['S&P 500'];
    if (us && us.corr_3m < 0.1) T.push(['US decoupling', `NIFTY’s 3-month correlation with the S&P 500 is ${fmt(us.corr_3m, 2)} vs ${fmt(us.corr_10y_avg, 2)} normally: India is trading on domestic flows and policy, so overnight Wall Street cues are less reliable right now.`]);
    const vr = R.vrp, lastV = vr[vr.length - 1], avgV = vr.slice(-12, -1).reduce((a, b) => a + b.premium, 0) / 11;
    T.push(['Option-seller edge is the thinnest on record', `In ${lastV.year} India VIX averaged only ${fmt(lastV.premium, 1)} vol points above realised volatility (10-year average ${fmt(avgV, 1)}), and VIX beat realised vol on just ${fmt(lastV.pct_days_vix_above_rv * 100, 0)}% of days. Crowded weekly option selling is compressing premiums, which is why the gate asks for a live straddle check.`]);
    const oi = R.overnight_intraday, recent = oi.slice(-2), old = oi.slice(0, -2);
    T.push(['The overnight drift has faded', `From 2011 to 2024, almost all of NIFTY’s gains came overnight (avg ${fmt(old.reduce((a, b) => a + b.overnight, 0) / old.length, 0)}%/yr) while intraday trading lost money (avg ${fmt(old.reduce((a, b) => a + b.intraday, 0) / old.length, 0)}%/yr). In ${recent.map(r => `${r.year}: ${fmt(r.overnight, 1)}% overnight`).join(', ')}. Buying the close and selling the open no longer works.`]);
    const cy = R.cycles;
    T.push(['RBI has started hiking', `Repo rate raised to ${fmt(R.state.repo, 2)}% on 7 Oct 2026, the first hike since Feb 2023, with “calibrated tightening”. In past hiking phases NIFTY returned ${fmt(cy['RBI hiking (6m)'].ann_return, 1)}%/yr vs ${fmt(cy['RBI on hold (6m)'].ann_return, 1)}% on hold and ${fmt(cy['RBI cutting (6m)'].ann_return, 1)}% while cutting. Expect choppier, range-bound index behaviour.`]);
    const dw = R.day_of_week;
    T.push(['Tuesday expiry changed the week', `Since NIFTY moved to Tuesday expiry (Sep 2025), average daily ranges fell to ~${fmt(dw.Tue['since Sep-2025 (Tue expiry)'].range, 2)}% (from ~${fmt(dw.Tue['2019-08/2025'].range, 2)}%). Expiry-day moves are smaller than many traders assume.`]);
    $('#trends').innerHTML = T.map(([a, b]) => `<div class="trend-card"><b>${a}</b><span class="small">${b}</span></div>`).join('');

    const fa = R.factors_all, fr = Object.fromEntries(R.factors_recent.map(f => [f.factor, f]));
    $('#factors').innerHTML = `<table class="tbl"><thead><tr><th>Overnight factor</th><th>Corr with gap</th><th>Last 2 yrs</th><th>Same-direction hit on big moves</th><th>NIFTY gap when factor in top 10%</th><th>…bottom 10%</th></tr></thead><tbody>
      ${fa.map(f => `<tr><td>${f.factor}</td><td>${fmt(f.corr_gap, 2)}</td><td>${fmt(fr[f.factor]?.corr_gap, 2)}</td><td>${fmt(f.big_move_hit * 100, 0)}%</td><td class="${cls(f.gap_when_factor_top10)}">${fmt(f.gap_when_factor_top10, 2)}%</td><td class="${cls(f.gap_when_factor_bottom10)}">${fmt(f.gap_when_factor_bottom10, 2)}%</td></tr>`).join('')}
      </tbody></table><p class="muted small">${fa[0].n} sessions 2011–2026. Concurrent Asia correlation with NIFTY’s day: ${Object.entries(R.concurrent_asia).map(([k, v]) => `${k} ${fmt(v, 2)}`).join(', ')}. Intraday correlations are near zero: overnight news is priced in at 9:15.</p>`;

    const cp = $('#corrpick'); Object.keys(rc).forEach(k => cp.append(el('option', { value: k }, k))); cp.value = 'Brent crude';
    const drawCorr = () => { const x = rc[cp.value]; chart('corrchart', () => ({ type: 'line', data: { labels: x.series.map(s => s[0]), datasets: [{ data: x.series.map(s => s[1]), borderColor: css('--c2'), pointRadius: 0, borderWidth: 1.6 }] }, options: { scales: { x: { ticks: { maxTicksLimit: 8 } }, y: { suggestedMin: -0.6, suggestedMax: 0.8 } } } })); };
    cp.addEventListener('change', drawCorr); drawCorr();

    const mp = $('#macropick'); Object.keys(R.macro).forEach(k => mp.append(el('option', { value: k }, `${k}: 20-session change`)));
    const drawMacro = () => { $('#macro').innerHTML = `<table class="tbl"><thead><tr><th>Bucket</th><th>Days</th><th>NIFTY next 5 d</th><th>Next 21 d</th><th>Up %</th><th>Daily vol</th></tr></thead><tbody>
      ${R.macro[mp.value].map(b => `<tr><td>${b.bucket}</td><td>${b.days}</td><td class="${cls(b.mean_fwd5)}">${fmt(b.mean_fwd5, 2)}%</td><td class="${cls(b.mean_fwd21)}">${fmt(b.mean_fwd21, 2)}%</td><td>${fmt(b.up_pct_fwd21 * 100, 0)}</td><td>${fmt(b.daily_vol, 2)}%</td></tr>`).join('')}</tbody></table>`; };
    mp.addEventListener('change', drawMacro); drawMacro();

    $('#cycles').innerHTML = `<table class="tbl"><thead><tr><th>Phase</th><th>Days</th><th>NIFTY %/yr</th><th>Daily vol</th><th>Avg VIX</th></tr></thead><tbody>
      ${Object.entries(cy).map(([k, x]) => `<tr><td>${k}</td><td>${x.days}</td><td class="${cls(x.ann_return)}">${fmt(x.ann_return, 1)}</td><td>${fmt(x.daily_vol, 2)}%</td><td>${fmt(x.avg_vix, 1)}</td></tr>`).join('')}</tbody></table>
      <p class="muted small">Fed phase uses the US 3-month T-bill as a policy-rate proxy (6-month change).</p>`;
    $('#eventstudy').innerHTML = `<table class="tbl"><thead><tr><th>Event</th><th>N</th><th>Avg |move|</th><th>Move ÷ VIX-implied</th><th>Beat implied</th><th>VIX change</th></tr></thead><tbody>
      ${R.events.map(e => `<tr><td>${e.name}</td><td>${e.n}</td><td>${fmt(e.avg_abs_move, 2)}%</td><td>${fmt(e.median_ratio_to_implied, 2)}×</td><td>${fmt(e.pct_beat_implied * 100, 0)}%</td><td>${fmt(e.avg_vix_change, 1)}%</td></tr>`).join('')}
      <tr><td>Normal day</td><td></td><td>${fmt(R.events_normal.avg_abs_move, 2)}%</td><td>${fmt(R.events_normal.median_ratio_to_implied, 2)}×</td><td></td><td></td></tr></tbody></table>
      <p class="muted small">Event days move more than normal days but usually less than options price in, then VIX drops (IV crush). Buying a straddle the day before lost money in ${fmt((1 - R.backtests.find(b => b.name.startsWith('Event')).win_rate) * 100, 0)}% of events.</p>`;

    $('#vixreg').innerHTML = `<table class="tbl"><thead><tr><th>India VIX</th><th>Time</th><th>Implied 1σ week</th><th>Realised |week|</th><th>Inside 1σ</th><th>Worst week</th><th>NIFTY next 21 d</th></tr></thead><tbody>
      ${R.vix_regimes.map(b => `<tr><td>${b.bucket}</td><td>${fmt(b.share_of_time * 100, 0)}%</td><td>${fmt(b.implied_1s_week, 2)}%</td><td>${fmt(b.realised_abs_week, 2)}%</td><td>${fmt(b.stayed_inside_1s * 100, 0)}%</td><td class="down">${fmt(b.worst_week, 1)}%</td><td class="${cls(b.mean_fwd21)}">${fmt(b.mean_fwd21, 2)}%</td></tr>`).join('')}</tbody></table>`;
    chart('vrpchart', () => ({ type: 'bar', data: { labels: vr.map(x => x.year), datasets: [{ data: vr.map(x => x.premium), backgroundColor: vr.map(x => (x.premium > 2 ? css('--good') : x.premium > 1 ? css('--warn') : css('--bad'))) }] }, options: { scales: { y: { title: { display: true, text: 'vol points' } } } } }));
    chart('onchart', () => ({ type: 'bar', data: { labels: oi.map(x => x.year), datasets: [
      { label: 'Overnight (gap)', data: oi.map(x => x.overnight), backgroundColor: css('--c4') },
      { label: 'Intraday (open→close)', data: oi.map(x => x.intraday), backgroundColor: css('--c3') }] }, options: { plugins: { legend: { display: true } }, scales: { y: { title: { display: true, text: '% per year' } } } } }));
    $('#dow').innerHTML = `<table class="tbl"><thead><tr><th>Day</th><th>Avg move 2019–Aug 2025</th><th>Range</th><th>Avg move since Sep 2025</th><th>Range</th></tr></thead><tbody>
      ${Object.entries(R.day_of_week).map(([d, x]) => { const a = x['2019-08/2025'], b = x['since Sep-2025 (Tue expiry)']; return `<tr><td>${d}</td><td class="${cls(a.mean)}">${fmt(a.mean, 2)}%</td><td>${fmt(a.range, 2)}%</td><td class="${cls(b.mean)}">${fmt(b.mean, 2)}%</td><td>${fmt(b.range, 2)}%</td></tr>`; }).join('')}</tbody></table>`;
  }

  // ------------------------------------------------------------------ NEWS
  async function loadNews(force) {
    $('#newslist').innerHTML = '<li class="muted">Loading headlines…</li>';
    try { S.news = await getJSON('/api/news' + (force ? '?t=' + Date.now() : '')); }
    catch (e) { $('#newslist').innerHTML = `<li class="down">News unavailable: ${e.message}</li>`; return; }
    const n = S.news, agg = n.last48h;
    const tone = agg.score > 5 ? ['up', 'positive'] : agg.score < -5 ? ['down', 'negative'] : ['', 'mixed'];
    $('#newsagg').innerHTML = `<div class="kv"><div><span>Headlines (48 h)</span><b>${agg.n}</b></div><div><span>Net tone</span><b class="${tone[0]}">${agg.score > 0 ? '+' : ''}${agg.score} · ${tone[1]}</b></div>
      ${Object.entries(agg.byTag).sort((a, b) => b[1].n - a[1].n).slice(0, 6).map(([k, x]) => `<div><span>${k}</span><b class="${cls(x.score)}">${x.n} · ${x.score > 0 ? '+' : ''}${x.score}</b></div>`).join('')}</div>
      <p class="muted small">Keyword scoring is crude and was not part of the backtest (no free historical news archive). Use it to spot what the market is talking about, not as a signal.${n.errors.length ? ' Feeds unavailable: ' + n.errors.join('; ') : ''}</p>`;
    const tagSel = $('#newstag'); tagSel.length = 1; Object.keys(agg.byTag).forEach(t => tagSel.append(el('option', { value: t }, t)));
    renderNews();
  }
  function renderNews() {
    const q = $('#newsfilter').value.toLowerCase(), tag = $('#newstag').value;
    const items = S.news.items.filter(i => (!q || i.title.toLowerCase().includes(q)) && (!tag || i.tags.includes(tag)));
    $('#newslist').innerHTML = items.map(i => `<li><span class="score ${i.sentiment > 0 ? 'p' : i.sentiment < 0 ? 'n' : 'z'}">${i.sentiment > 0 ? '+' : ''}${i.sentiment}</span>
      <div><a href="${i.link}" target="_blank" rel="noopener">${i.title.replace(/</g, '&lt;')}</a><div class="muted small">${i.source} · ${new Date(i.date).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata', hour12: false, dateStyle: 'medium', timeStyle: 'short' })} ${i.tags.map(t => `<span class="chip">${t}</span>`).join('')}</div></div></li>`).join('') || '<li class="muted">No headlines match.</li>';
  }
  $('#newsfilter').addEventListener('input', () => S.news && renderNews());
  $('#newstag').addEventListener('change', () => S.news && renderNews());

  // ------------------------------------------------------------------ JOURNAL
  const J = () => store.get('journal', []);
  $('#logplan').addEventListener('click', () => {
    if (!S.plan) return alert('Live plan not ready yet.');
    const p = S.plan;
    const j = J(); j.unshift({ id: Date.now(), logged: new Date().toISOString().slice(0, 10), expiry: p.expiry, structure: p.structure, verdict: S.verdict?.k,
      taken: S.verdict?.k !== 'bad', spot: Math.round(p.spot), vix: +p.vix.toFixed(2), legs: p.legs, credit: Math.round(p.credit), settle: null, pnl: null });
    store.set('journal', j); renderJournal();
  });
  function settle(entry, close) {
    const gross = L.payoffAt(entry.legs, close, LOT);
    const ch = L.charges(entry.legs, LOT, close).total;
    return Math.round(gross - ch);
  }
  function renderJournal() {
    const j = J();
    const done = j.filter(x => x.pnl != null && x.taken);
    const tot = done.reduce((a, b) => a + b.pnl, 0);
    const bt = S.results?.backtests.find(b => b.name === 'Iron condor + macro guard');
    $('#jstats').innerHTML = `<div class="kv"><div><span>Plans logged</span><b>${j.length}</b></div><div><span>Settled trades</span><b>${done.length}</b></div>
      <div><span>Win rate</span><b>${done.length ? fmt(done.filter(x => x.pnl > 0).length / done.length * 100, 0) + '%' : '—'}</b></div>
      <div><span>Total P&L / lot</span><b class="${cls(tot)}">${rs(tot)}</b></div><div><span>Avg / trade</span><b>${done.length ? rs(tot / done.length) : '—'}</b></div>
      <div><span>Backtest avg</span><b>${bt ? rs(bt.avg_pnl_rs) : '—'}</b></div></div>
      <p class="muted small">Paper-trade at least 12–20 weeks. If your forward average is well below the backtest, the model premiums were too optimistic for real fills.</p>`;
    $('#jtable').innerHTML = `<thead><tr><th>Logged</th><th>Expiry</th><th>Gate</th><th>Legs</th><th>Credit</th><th>Expiry close</th><th>P&L / lot</th><th></th></tr></thead><tbody>
      ${j.map(x => `<tr data-id="${x.id}"><td>${x.logged}</td><td>${x.expiry}</td><td><span class="dot ${x.verdict}" style="display:inline-block"></span> ${x.taken ? 'traded' : 'stood aside'}</td>
        <td>${x.legs.map(l => `${l.side[0]}${l.type === 'C' ? 'CE' : 'PE'} ${l.strike}@${l.premium}`).join('<br>')}</td><td>${rs(x.credit)}</td>
        <td><input type="number" step="0.05" value="${x.settle ?? ''}" data-settle placeholder="close"></td><td class="${cls(x.pnl)}">${x.pnl == null ? '—' : rs(x.pnl)}</td>
        <td><button class="btn ghost" data-toggle>${x.taken ? 'mark skipped' : 'mark traded'}</button> <button class="btn ghost" data-del>✕</button></td></tr>`).join('')}</tbody>`;
    $('#jtable').querySelectorAll('tr[data-id]').forEach(tr => {
      const id = +tr.dataset.id;
      const upd = fn => { const all = J(); const e = all.find(x => x.id === id); fn(e, all); store.set('journal', all.filter(Boolean)); renderJournal(); };
      tr.querySelector('[data-settle]').addEventListener('change', ev => upd(e => { const c = +ev.target.value; e.settle = c || null; e.pnl = c ? settle(e, c) : null; }));
      tr.querySelector('[data-toggle]').onclick = () => upd(e => { e.taken = !e.taken; });
      tr.querySelector('[data-del]').onclick = () => { store.set('journal', J().filter(x => x.id !== id)); renderJournal(); };
    });
  }
  $('#exportj').addEventListener('click', () => {
    const rows = [['logged', 'expiry', 'structure', 'gate', 'taken', 'spot', 'vix', 'legs', 'credit', 'settle', 'pnl']]
      .concat(J().map(x => [x.logged, x.expiry, x.structure, x.verdict, x.taken, x.spot, x.vix, x.legs.map(l => `${l.side}:${l.type}:${l.strike}:${l.premium}`).join('|'), x.credit, x.settle ?? '', x.pnl ?? '']));
    const a = el('a', { href: URL.createObjectURL(new Blob([rows.map(r => r.join(',')).join('\n')], { type: 'text/csv' })), download: 'option-desk-journal.csv' });
    a.click();
  });
  $('#importj').addEventListener('change', async e => {
    const f = e.target.files[0]; if (!f) return;
    const lines = (await f.text()).split(/\r?\n/).slice(1).filter(Boolean);
    const imported = lines.map((ln, i) => { const c = ln.split(','); return { id: Date.now() + i, logged: c[0], expiry: c[1], structure: c[2], verdict: c[3], taken: c[4] === 'true', spot: +c[5], vix: +c[6],
      legs: c[7].split('|').map(s => { const [side, type, strike, premium] = s.split(':'); return { side, type, strike: +strike, premium: +premium, lots: 1 }; }), credit: +c[8], settle: c[9] ? +c[9] : null, pnl: c[10] ? +c[10] : null }; });
    store.set('journal', [...imported, ...J()]); renderJournal();
  });

  // ------------------------------------------------------------------ ABOUT
  function renderAbout() {
    const R = S.results, ic = R.backtests.find(b => b.name === 'Iron condor + macro guard'), ns = R.backtests.find(b => b.name.startsWith('Short strangle')), ls = R.backtests.find(b => b.name.startsWith('Long ATM'));
    $('#about').innerHTML = `
      <h2>Can this make money?</h2>
      <p>Honestly: possibly a modest amount, with real risk, and only if live option prices match the model. In the backtest the best rule set (iron condor + macro guard) averaged ${rs(ic.avg_pnl_rs)} per lot per traded week, about ${fmt(ic.trades / 15.8, 0)} weeks a year, with a worst week of ${rs(ic.worst_rs)} and a drawdown of ${rs(ic.max_dd_rs)} on roughly ₹${fmt(ic.avg_risk_rs / 1000, 0)}k of risk per lot. That is a thin edge. It falls to about ₹160 per week if real weekly IV is 0.85 × India VIX, and 2026’s option premium has been the lowest on record.</p>
      <p>What reliably loses: buying weekly options (${rs(ls.avg_pnl_rs)} per week on average, ${fmt(ls.win_rate * 100, 0)}% win rate) and selling naked strangles (worst week ${rs(ns.worst_rs)} per lot, which can wipe out a small account).</p>
      <h2>Daily routine</h2>
      <ol>
        <li><b>8:30–9:10 IST:</b> open Today. Read the gap model and the trade gate. Check News for anything the model can’t see.</li>
        <li><b>Entry day</b> (4 sessions before expiry, usually Wednesday): if the gate is green, load the live straddle (Option chain tab or broker) and re-check. Use real bid/ask premiums.</li>
        <li><b>Size</b> with 1–2% of capital at risk per trade. Never more lots than the plan shows.</li>
        <li><b>Manage:</b> exit if NIFTY closes beyond a short strike, or the position loses 2× the credit. Don’t roll losers into events.</li>
        <li><b>Log</b> every plan in the Journal, including stand-aside weeks, and settle at expiry.</li>
      </ol>
      <h2>Method</h2>
      <ul>
        <li><b>Data:</b> Yahoo Finance daily history: NIFTY and India VIX from 2008, plus S&P 500, Nasdaq, Dow, US VIX, DXY, USD/INR, Brent, WTI, gold, silver, copper, natural gas, US 3M / 10Y / 30Y yields, DAX, FTSE, Nikkei, Hang Seng, Shanghai and Bitcoin. NIFTY opens before 2011 are unreliable on Yahoo and are excluded from gap tests.</li>
        <li><b>Timing:</b> a factor’s overnight change is its last print before the Indian session versus its last print before the previous session, so nothing from the future leaks in.</li>
        <li><b>Gap model:</b> OLS on 9 factors, winsorised at 1/99%, trained 2011–2019, scored out-of-sample 2020–2026.</li>
        <li><b>Rates:</b> RBI repo history from RBI announcements (2008 – Oct 2026). Fed policy is proxied by the 3-month T-bill, because FRED was unreachable from the research machine.</li>
        <li><b>Options:</b> NSE has no free historical option-chain archive, so premiums are Black-Scholes on India VIX × 0.95 with a put skew. Weekly NIFTY options only exist from 2019; earlier years show what a 4-day option would have done. Costs: 0.75 pt slippage per leg, 0.15% STT on sold premium and on ITM exercise, exchange fees + GST, stamp duty, ₹20 per leg.</li>
        <li><b>Not tested:</b> news sentiment (no free historical archive), FII/DII daily flows (NSE archive blocked), and intraday stops (daily bars only). Treat those parts of the app as context.</li>
      </ul>
      <h2>Rules that protect you</h2>
      <ul><li>Defined risk only. No naked short options.</li><li>No trades through RBI, Budget or election days.</li><li>Stand aside when the macro guard is red. That is part of the edge, not a missed opportunity.</li><li>Under SEBI rules, retail API algos need a registered app and static IP. This app never places orders.</li></ul>`;
  }

  boot().catch(e => { $('#stamp').innerHTML = `<span class="down">Failed to load: ${e.message}</span>`; console.error(e); });
  window.addEventListener('resize', () => { clearTimeout(window.__rz); window.__rz = setTimeout(redrawCharts, 200); });
})();
