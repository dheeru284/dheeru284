"use client";

import { useEffect, useRef, useState } from "react";
import type { DashboardCandle, StrategyConfig } from "@/lib/types";
import { BARS_PER_SESSION, clock, price } from "@/lib/format";

const PRICE_H = 360;
const RSI_H = 130;
const PAD = { left: 8, right: 84, top: 12, bottom: 22 };

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(900);
  useEffect(() => {
    if (!ref.current) return;
    const obs = new ResizeObserver(([entry]) => setWidth(Math.max(280, entry.contentRect.width)));
    obs.observe(ref.current);
    return () => obs.disconnect();
  }, []);
  return [ref, width] as const;
}

function ticks(min: number, max: number, count: number): number[] {
  const raw = (max - min) / count;
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

export function PriceChart({ candles, config }: { candles: DashboardCandle[]; config: StrategyConfig }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);

  const innerW = width - PAD.left - PAD.right;
  const slot = innerW / BARS_PER_SESSION;
  const x = (i: number) => PAD.left + slot * (i + 0.5);

  const values = candles.flatMap((c) => [c.high, c.low, c.ema_fast, c.ema_slow, c.vwap].filter((v): v is number => v != null));
  const lo = values.length ? Math.min(...values) : 0;
  const hi = values.length ? Math.max(...values) : 1;
  const span = Math.max(hi - lo, 1);
  const yMin = lo - span * 0.06;
  const yMax = hi + span * 0.06;
  const py = (v: number) => PAD.top + ((yMax - v) / (yMax - yMin)) * (PRICE_H - PAD.top - PAD.bottom);
  const ry = (v: number) => 8 + ((100 - v) / 100) * (RSI_H - 8 - PAD.bottom);

  const onMove = (e: React.MouseEvent<SVGSVGElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const i = Math.floor((e.clientX - box.left - PAD.left) / slot);
    setHover(i >= 0 && i < candles.length ? i : null);
  };
  const h = hover != null ? candles[hover] : null;
  const timeLabels = candles.map((c, i) => [i, c.timestamp] as const).filter(([i]) => i % (slot * 12 >= 56 ? 12 : 24) === 0);
  const bodyW = Math.max(1, slot * 0.62);

  return (
    <div ref={ref} className="chart">
      <div className="legend">
        <span className="key ema-fast">EMA {config.ema_fast}</span>
        <span className="key ema-slow">EMA {config.ema_slow}</span>
        <span className="key vwap">VWAP</span>
        {h && (
          <span className="readout">
            {clock(h.timestamp)} · O {price(h.open)} H {price(h.high)} L {price(h.low)} C {price(h.close)} · Vol{" "}
            {h.volume.toLocaleString("en-IN")} · RSI {h.rsi?.toFixed(1) ?? "—"}
          </span>
        )}
      </div>

      <svg width={width} height={PRICE_H} onMouseMove={onMove} onMouseLeave={() => setHover(null)} role="img"
        aria-label="Five-minute candlestick chart with EMA and VWAP overlays">
        <text x={PAD.left + innerW / 2} y={PRICE_H / 2} className="watermark" textAnchor="middle" dominantBaseline="middle"
          fontSize={Math.min(84, innerW / 6.5)}>
          SIMULATED
        </text>
        {ticks(yMin, yMax, 5).map((v) => (
          <g key={v}>
            <line x1={PAD.left} x2={PAD.left + innerW} y1={py(v)} y2={py(v)} className="grid" />
            <text x={width - PAD.right + 6} y={py(v)} className="axis" dominantBaseline="middle">{v.toLocaleString("en-IN")}</text>
          </g>
        ))}
        {timeLabels.map(([i, ts]) => (
          <text key={ts} x={x(i)} y={PRICE_H - 6} className="axis" textAnchor={i === 0 ? "start" : "middle"}>{clock(ts)}</text>
        ))}
        {candles.map((c, i) => {
          const up = c.close >= c.open;
          const top = py(Math.max(c.open, c.close));
          return (
            <g key={c.timestamp} className={up ? "up" : "down"}>
              <line x1={x(i)} x2={x(i)} y1={py(c.high)} y2={py(c.low)} className="wick" />
              <rect x={x(i) - bodyW / 2} y={top} width={bodyW} height={Math.max(1, py(Math.min(c.open, c.close)) - top)} className="body" />
            </g>
          );
        })}
        <path d={line(candles.map((c, i) => [x(i), c.vwap == null ? null : py(c.vwap)]))} className="series vwap" />
        <path d={line(candles.map((c, i) => [x(i), c.ema_slow == null ? null : py(c.ema_slow)]))} className="series ema-slow" />
        <path d={line(candles.map((c, i) => [x(i), c.ema_fast == null ? null : py(c.ema_fast)]))} className="series ema-fast" />
        {candles.length > 0 && (() => {
          const last = candles[candles.length - 1];
          return (
            <g>
              <line x1={PAD.left} x2={PAD.left + innerW} y1={py(last.close)} y2={py(last.close)} className="last-line" />
              <rect x={width - PAD.right + 2} y={py(last.close) - 9} width={PAD.right - 4} height={18} rx={3} className="last-tag" />
              <text x={width - PAD.right + 6} y={py(last.close)} className="last-text" dominantBaseline="middle">{price(last.close)}</text>
            </g>
          );
        })()}
        {hover != null && <line x1={x(hover)} x2={x(hover)} y1={PAD.top} y2={PRICE_H - PAD.bottom} className="crosshair" />}
      </svg>

      <div className="legend sub">
        <span className="key rsi">RSI {config.rsi_period}</span>
        <span className="band long">long band {config.long_rsi_min}–{config.long_rsi_max}</span>
        <span className="band short">short band {config.short_rsi_min}–{config.short_rsi_max}</span>
      </div>
      <svg width={width} height={RSI_H} onMouseMove={onMove} onMouseLeave={() => setHover(null)} role="img" aria-label="RSI 14">
        <rect x={PAD.left} width={innerW} y={ry(config.long_rsi_max)} height={ry(config.long_rsi_min) - ry(config.long_rsi_max)} className="zone long" />
        <rect x={PAD.left} width={innerW} y={ry(config.short_rsi_max)} height={ry(config.short_rsi_min) - ry(config.short_rsi_max)} className="zone short" />
        {[30, 50, 70].map((v) => (
          <g key={v}>
            <line x1={PAD.left} x2={PAD.left + innerW} y1={ry(v)} y2={ry(v)} className={v === 50 ? "grid" : "grid strong"} />
            <text x={width - PAD.right + 6} y={ry(v)} className="axis" dominantBaseline="middle">{v}</text>
          </g>
        ))}
        <path d={line(candles.map((c, i) => [x(i), c.rsi == null ? null : ry(c.rsi)]))} className="series rsi" />
        {hover != null && <line x1={x(hover)} x2={x(hover)} y1={8} y2={RSI_H - PAD.bottom} className="crosshair" />}
      </svg>
    </div>
  );
}
