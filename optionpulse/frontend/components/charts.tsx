"use client";

import { useState } from "react";
import type { Candle, Trade } from "@/lib/types";
import { BARS_PER_SESSION, STRATEGY_COLORS, clock, dateTime, price, signed } from "@/lib/format";
import { useWidth } from "@/lib/useWidth";

const PAD = { left: 8, right: 76, top: 14, bottom: 24 };

function ticks(min: number, max: number, count: number): number[] {
  const raw = (max - min) / count || 1;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw;
  const out = [];
  for (let v = Math.ceil(min / step) * step; v <= max; v += step) out.push(v);
  return out;
}

function line(points: [number, number | null][]): string {
  let d = "";
  let pen = false;
  for (const [x, y] of points) {
    if (y == null) { pen = false; continue; }
    d += `${pen ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`;
    pen = true;
  }
  return d;
}

export function PriceChart({ candles, trades = [], watermark }: { candles: Candle[]; trades?: Trade[]; watermark?: string }) {
  const [ref, width] = useWidth<HTMLDivElement>(900);
  const [hover, setHover] = useState<number | null>(null);
  const PRICE_H = 340;
  const RSI_H = 110;

  const innerW = width - PAD.left - PAD.right;
  const slot = innerW / BARS_PER_SESSION;
  const x = (i: number) => PAD.left + slot * (i + 0.5);
  const index = new Map(candles.map((c, i) => [new Date(c.timestamp).getTime(), i]));
  const at = (ms: number) => index.get(ms) ?? null;

  const values = candles.flatMap((c) => [c.high, c.low, c.ema_fast, c.ema_slow, c.vwap].filter((v): v is number => v != null));
  const lo = values.length ? Math.min(...values) : 0;
  const hi = values.length ? Math.max(...values) : 1;
  const span = Math.max(hi - lo, 1);
  const yMin = lo - span * 0.08;
  const yMax = hi + span * 0.08;
  const py = (v: number) => PAD.top + ((yMax - v) / (yMax - yMin)) * (PRICE_H - PAD.top - PAD.bottom);
  const ry = (v: number) => 8 + ((100 - v) / 100) * (RSI_H - 8 - PAD.bottom);

  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const i = Math.floor((e.clientX - box.left - PAD.left) / slot);
    setHover(i >= 0 && i < candles.length ? i : null);
  };
  const h = hover != null ? candles[hover] : null;
  const labelEvery = slot * 12 >= 56 ? 12 : 24;
  const bodyW = Math.max(1.5, slot * 0.6);

  return (
    <div ref={ref} className="chart">
      <div className="legend">
        <span className="key ema-fast">EMA 9</span>
        <span className="key ema-slow">EMA 21</span>
        <span className="key vwap">VWAP</span>
        {trades.length > 0 && <span className="key-text">▲▼ paper entries · ● exits</span>}
        <span className="readout">
          {h ? `${clock(h.timestamp)}  O ${price(h.open)}  H ${price(h.high)}  L ${price(h.low)}  C ${price(h.close)}  RSI ${h.rsi?.toFixed(1) ?? "—"}` : "Hover the chart for candle details"}
        </span>
      </div>
      <svg width={width} height={PRICE_H} onMouseMove={onMove} onMouseLeave={() => setHover(null)} role="img"
        aria-label="Five-minute NIFTY candles with EMA 9, EMA 21 and VWAP">
        {watermark && (
          <text x={PAD.left + innerW / 2} y={PRICE_H / 2} className="watermark" textAnchor="middle"
            dominantBaseline="middle" fontSize={Math.min(76, innerW / 7)}>{watermark}</text>
        )}
        {ticks(yMin, yMax, 5).map((v) => (
          <g key={v}>
            <line x1={PAD.left} x2={PAD.left + innerW} y1={py(v)} y2={py(v)} className="grid" />
            <text x={width - PAD.right + 8} y={py(v)} className="axis" dominantBaseline="middle">{v.toLocaleString("en-IN")}</text>
          </g>
        ))}
        {candles.map((c, i) => i % labelEvery === 0 && (
          <text key={c.timestamp} x={x(i)} y={PRICE_H - 6} className="axis" textAnchor={i === 0 ? "start" : "middle"}>{clock(c.timestamp)}</text>
        ))}
        {candles.map((c, i) => {
          const top = py(Math.max(c.open, c.close));
          return (
            <g key={c.timestamp} className={c.close >= c.open ? "up" : "down"}>
              <line x1={x(i)} x2={x(i)} y1={py(c.high)} y2={py(c.low)} className="wick" />
              <rect x={x(i) - bodyW / 2} y={top} width={bodyW} rx={1} height={Math.max(1, py(Math.min(c.open, c.close)) - top)} className="body" />
            </g>
          );
        })}
        <path d={line(candles.map((c, i) => [x(i), c.vwap == null ? null : py(c.vwap)]))} className="series vwap" />
        <path d={line(candles.map((c, i) => [x(i), c.ema_slow == null ? null : py(c.ema_slow)]))} className="series ema-slow" />
        <path d={line(candles.map((c, i) => [x(i), c.ema_fast == null ? null : py(c.ema_fast)]))} className="series ema-fast" />
        {trades.map((t) => {
          const ei = at(new Date(t.entry_time).getTime());
          const xi = t.exit_time ? at(new Date(t.exit_time).getTime() - 5 * 60_000) : null; // exit time is the candle's end
          if (ei == null) return null;
          const color = STRATEGY_COLORS[t.strategy_id] ?? "var(--ink)";
          const ey = py(t.entry_price);
          const up = t.side === "LONG";
          return (
            <g key={t.id}>
              {xi != null && t.exit_price != null && (
                <>
                  <line x1={x(ei)} y1={ey} x2={x(xi)} y2={py(t.exit_price)} stroke={color} strokeDasharray="3 3" strokeWidth={1.2} />
                  <circle cx={x(xi)} cy={py(t.exit_price)} r={4} fill="var(--card)" stroke={color} strokeWidth={2} />
                </>
              )}
              <path d={up ? `M${x(ei)},${ey - 1} l-6,10 h12 z` : `M${x(ei)},${ey + 1} l-6,-10 h12 z`} fill={color}>
                <title>{`${t.strategy_id} ${t.side} @ ${price(t.entry_price)} → ${t.exit_reason} ${signed(t.points)} pts`}</title>
              </path>
            </g>
          );
        })}
        {candles.length > 0 && (() => {
          const last = candles[candles.length - 1];
          return (
            <g>
              <line x1={PAD.left} x2={PAD.left + innerW} y1={py(last.close)} y2={py(last.close)} className="last-line" />
              <rect x={width - PAD.right + 3} y={py(last.close) - 10} width={PAD.right - 6} height={20} rx={10} className="last-tag" />
              <text x={width - PAD.right + 3 + (PAD.right - 6) / 2} y={py(last.close)} className="last-text" textAnchor="middle" dominantBaseline="middle">{price(last.close, 1)}</text>
            </g>
          );
        })()}
        {hover != null && <line x1={x(hover)} x2={x(hover)} y1={PAD.top} y2={PRICE_H - PAD.bottom} className="crosshair" />}
      </svg>
      <div className="legend sub"><span className="key rsi">RSI 14</span><span className="key-text">30 · 50 · 70</span></div>
      <svg width={width} height={RSI_H} onMouseMove={onMove} onMouseLeave={() => setHover(null)} role="img" aria-label="RSI 14">
        <rect x={PAD.left} width={innerW} y={ry(70)} height={ry(30) - ry(70)} className="zone" />
        {[30, 50, 70].map((v) => (
          <g key={v}>
            <line x1={PAD.left} x2={PAD.left + innerW} y1={ry(v)} y2={ry(v)} className="grid" />
            <text x={width - PAD.right + 8} y={ry(v)} className="axis" dominantBaseline="middle">{v}</text>
          </g>
        ))}
        <path d={line(candles.map((c, i) => [x(i), c.rsi == null ? null : ry(c.rsi)]))} className="series rsi" />
        {hover != null && <line x1={x(hover)} x2={x(hover)} y1={8} y2={RSI_H - PAD.bottom} className="crosshair" />}
      </svg>
    </div>
  );
}

export function Sparkline({ values, rising }: { values: number[]; rising: "good" | "bad" | "flat" }) {
  if (values.length < 2) return <svg className="spark" viewBox="0 0 100 28" aria-hidden />;
  const lo = Math.min(...values), hi = Math.max(...values), span = hi - lo || 1;
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * 100},${26 - ((v - lo) / span) * 24}`);
  return (
    <svg className={`spark ${rising}`} viewBox="0 0 100 28" preserveAspectRatio="none" aria-hidden>
      <polyline points={pts.join(" ")} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

export interface EquitySeries { id: string; label: string; color: string; points: { time: string; points: number }[]; dashed?: boolean }

export function EquityChart({ series, height = 260 }: { series: EquitySeries[]; height?: number }) {
  const [ref, width] = useWidth<HTMLDivElement>(800);
  const [hover, setHover] = useState<{ x: number; t: number } | null>(null);
  const all = series.flatMap((s) => s.points);
  if (all.length === 0) return <div ref={ref} className="empty-chart">No closed trades in this window yet.</div>;
  const times = all.map((p) => new Date(p.time).getTime());
  const t0 = Math.min(...times), t1 = Math.max(...times);
  const vals = [0, ...all.map((p) => p.points)];
  const lo = Math.min(...vals), hi = Math.max(...vals), span = hi - lo || 1;
  const innerW = width - PAD.left - PAD.right;
  const px = (t: number) => PAD.left + (t1 === t0 ? innerW / 2 : ((t - t0) / (t1 - t0)) * innerW);
  const py = (v: number) => PAD.top + ((hi + span * 0.1 - v) / (span * 1.2)) * (height - PAD.top - PAD.bottom);

  return (
    <div ref={ref} className="chart">
      <svg width={width} height={height} role="img" aria-label="Cumulative points over time"
        onMouseMove={(e) => { const b = e.currentTarget.getBoundingClientRect(); const xx = e.clientX - b.left; setHover({ x: xx, t: t0 + ((xx - PAD.left) / innerW) * (t1 - t0) }); }}
        onMouseLeave={() => setHover(null)}>
        {ticks(lo, hi, 4).map((v) => (
          <g key={v}>
            <line x1={PAD.left} x2={PAD.left + innerW} y1={py(v)} y2={py(v)} className={v === 0 ? "grid zero" : "grid"} />
            <text x={width - PAD.right + 8} y={py(v)} className="axis" dominantBaseline="middle">{signed(v, 0)}</text>
          </g>
        ))}
        {series.map((s) => {
          const pts: [number, number][] = [[px(new Date(s.points[0]?.time ?? t0).getTime()), py(0)],
            ...s.points.map((p) => [px(new Date(p.time).getTime()), py(p.points)] as [number, number])];
          return (
            <path key={s.id} d={pts.map(([a, b], i) => `${i ? "L" : "M"}${a.toFixed(1)},${b.toFixed(1)}`).join("")}
              fill="none" stroke={s.color} strokeWidth={2.4} strokeLinejoin="round" strokeDasharray={s.dashed ? "6 4" : undefined} />
          );
        })}
        {hover && hover.x > PAD.left && hover.x < PAD.left + innerW && (
          <g>
            <line x1={hover.x} x2={hover.x} y1={PAD.top} y2={height - PAD.bottom} className="crosshair" />
            {series.map((s, k) => {
              const last = [...s.points].reverse().find((p) => new Date(p.time).getTime() <= hover.t);
              return (
                <text key={s.id} x={Math.min(hover.x + 8, width - 200)} y={PAD.top + 14 + k * 16} className="hover-text" fill={s.color}>
                  {s.label}: {signed(last?.points ?? 0, 1)} pts
                </text>
              );
            })}
            <text x={Math.min(hover.x + 8, width - 200)} y={height - PAD.bottom - 6} className="axis">{dateTime(new Date(hover.t).toISOString())}</text>
          </g>
        )}
      </svg>
    </div>
  );
}
