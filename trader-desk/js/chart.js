// Minimal canvas charts: candles + overlays + RSI pane, a histogram, and a line.
// No library, so the site has zero runtime dependencies.
(function (TD) {
  'use strict';

  function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

  function setup(canvas, height) {
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth || canvas.parentElement.clientWidth;
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(height * dpr);
    canvas.style.height = height + 'px';
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, height);
    ctx.font = '11px ui-monospace, SFMono-Regular, Menlo, monospace';
    return { ctx, w, h: height };
  }

  // bars: full series; scan.series: aligned indicator arrays; lines: [{price, label, color}]
  function candles(canvas, bars, scan, lines, nShow = 160) {
    const { ctx, w, h } = setup(canvas, 420);
    const off = Math.max(0, bars.length - nShow);
    const view = bars.slice(off);
    const padR = 64, priceH = 290, volH = 40, rsiTop = priceH + volH + 14, rsiH = h - rsiTop - 6;
    const lo = Math.min(...view.map(b => b.l), ...lines.map(l => l.price));
    const hi = Math.max(...view.map(b => b.h), ...lines.map(l => l.price));
    const pad = (hi - lo) * 0.05;
    const y = p => 8 + (priceH - 16) * (1 - (p - (lo - pad)) / ((hi + pad) - (lo - pad)));
    const bw = (w - padR) / view.length;
    const x = i => i * bw + bw / 2;
    const up = css('--up'), down = css('--down'), grid = css('--grid'), muted = css('--muted');

    // Grid and price axis.
    ctx.strokeStyle = grid; ctx.fillStyle = muted; ctx.lineWidth = 1;
    for (let k = 0; k <= 5; k++) {
      const p = lo + (hi - lo) * k / 5, yy = y(p);
      ctx.beginPath(); ctx.moveTo(0, yy); ctx.lineTo(w - padR, yy); ctx.stroke();
      ctx.fillText(p.toFixed(2), w - padR + 6, yy + 4);
    }
    // Volume.
    const vmax = Math.max(...view.map(b => b.v)) || 1;
    view.forEach((b, i) => {
      ctx.fillStyle = (b.c >= b.o ? up : down) + '55';
      const vh = (b.v / vmax) * volH;
      ctx.fillRect(x(i) - bw * 0.35, priceH + volH - vh, bw * 0.7, vh);
    });
    // Candles.
    view.forEach((b, i) => {
      const col = b.c >= b.o ? up : down;
      ctx.strokeStyle = col; ctx.fillStyle = col;
      ctx.beginPath(); ctx.moveTo(x(i), y(b.h)); ctx.lineTo(x(i), y(b.l)); ctx.stroke();
      const top = y(Math.max(b.o, b.c)), bot = y(Math.min(b.o, b.c));
      ctx.fillRect(x(i) - bw * 0.35, top, Math.max(1, bw * 0.7), Math.max(1, bot - top));
    });
    // Moving averages.
    const series = [['sma20', css('--s1')], ['sma50', css('--s2')], ['sma200', css('--s3')]];
    for (const [k, col] of series) {
      const s = scan.series[k].slice(off);
      ctx.strokeStyle = col; ctx.lineWidth = 1.5; ctx.beginPath();
      let started = false;
      s.forEach((v, i) => {
        if (isNaN(v)) return;
        if (!started) { ctx.moveTo(x(i), y(v)); started = true; } else ctx.lineTo(x(i), y(v));
      });
      ctx.stroke();
    }
    // Horizontal levels.
    ctx.lineWidth = 1;
    for (const l of lines) {
      ctx.strokeStyle = l.color; ctx.setLineDash(l.dash ? [4, 4] : []);
      ctx.beginPath(); ctx.moveTo(0, y(l.price)); ctx.lineTo(w - padR, y(l.price)); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = l.color;
      ctx.fillText(l.label, 4, y(l.price) - 3);
    }
    // RSI pane.
    const ry = v => rsiTop + rsiH * (1 - v / 100);
    ctx.strokeStyle = grid;
    for (const v of [30, 70]) { ctx.beginPath(); ctx.moveTo(0, ry(v)); ctx.lineTo(w - padR, ry(v)); ctx.stroke(); ctx.fillStyle = muted; ctx.fillText(String(v), w - padR + 6, ry(v) + 4); }
    ctx.fillText('RSI 14', 4, rsiTop + 10);
    ctx.strokeStyle = css('--accent'); ctx.lineWidth = 1.5; ctx.beginPath();
    scan.series.rsi.slice(off).forEach((v, i) => { if (!isNaN(v)) (i === 0 ? ctx.moveTo : ctx.lineTo).call(ctx, x(i), ry(v)); });
    ctx.stroke();
    // Date labels.
    ctx.fillStyle = muted;
    for (let i = 0; i < view.length; i += Math.ceil(view.length / 6)) ctx.fillText(view[i].t.slice(2), x(i) - 20, priceH + volH + 11);
  }

  function histogram(canvas, values, bins = 40) {
    const { ctx, w, h } = setup(canvas, 180);
    const lo = values[0], hi = values[values.length - 1];
    if (!(hi > lo)) return;
    const counts = new Array(bins).fill(0);
    for (const v of values) counts[Math.min(bins - 1, Math.floor((v - lo) / (hi - lo) * bins))]++;
    const cmax = Math.max(...counts), bw = w / bins;
    counts.forEach((c, i) => {
      const mid = lo + (i + 0.5) * (hi - lo) / bins;
      ctx.fillStyle = mid >= 0 ? css('--up') : css('--down');
      const bh = (c / cmax) * (h - 24);
      ctx.fillRect(i * bw + 1, h - 18 - bh, bw - 2, bh);
    });
    ctx.fillStyle = css('--muted');
    ctx.fillText(fmtMoney(lo), 2, h - 4);
    const t = fmtMoney(hi); ctx.fillText(t, w - ctx.measureText(t).width - 2, h - 4);
    if (lo < 0 && hi > 0) {
      const zx = (-lo) / (hi - lo) * w;
      ctx.strokeStyle = css('--fg'); ctx.setLineDash([3, 3]);
      ctx.beginPath(); ctx.moveTo(zx, 0); ctx.lineTo(zx, h - 18); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillText('0', zx + 3, 10);
    }
  }

  // series: [{label, color, points: [number]}] sharing one x axis.
  function lines(canvas, series, height = 200) {
    const { ctx, w, h } = setup(canvas, height);
    const all = series.flatMap(s => s.points);
    const lo = Math.min(...all), hi = Math.max(...all);
    const y = v => 6 + (h - 24) * (1 - (v - lo) / ((hi - lo) || 1));
    ctx.fillStyle = css('--muted');
    ctx.fillText(lo.toFixed(2), 2, h - 4); ctx.fillText(hi.toFixed(2), 2, 14);
    series.forEach((s, k) => {
      const x = i => (i / (s.points.length - 1)) * (w - 2) + 1;
      ctx.strokeStyle = s.color; ctx.lineWidth = 1.5; ctx.beginPath();
      s.points.forEach((v, i) => (i === 0 ? ctx.moveTo : ctx.lineTo).call(ctx, x(i), y(v)));
      ctx.stroke();
      ctx.fillStyle = s.color; ctx.fillText(s.label, w - 160, 14 + k * 14);
    });
  }

  function fmtMoney(v) {
    const s = Math.abs(v) >= 1000 ? Math.abs(v).toLocaleString(undefined, { maximumFractionDigits: 0 }) : Math.abs(v).toFixed(2);
    return (v < 0 ? '-$' : '$') + s;
  }

  TD.chart = { candles, histogram, lines, fmtMoney };
})(window.TD = window.TD || {});
