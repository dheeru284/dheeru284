"use client";

import { useEffect, useState } from "react";
import { fetchDashboard } from "@/lib/api";
import { BARS_PER_SESSION, barEnd, clock, day } from "@/lib/format";
import type { Dashboard } from "@/lib/types";
import { PriceChart } from "./PriceChart";
import { SignalPanel } from "./SignalPanel";

const LIVE_REFRESH_MS = 15_000;

type Mode = { kind: "live" } | { kind: "replay"; day: string; bar: number };

export function DashboardView() {
  const [mode, setMode] = useState<Mode>({ kind: "live" });
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);

  const asOf = mode.kind === "replay" ? barEnd(mode.day, mode.bar) : undefined;

  useEffect(() => {
    const ctrl = new AbortController();
    const load = () =>
      fetchDashboard({ symbol: "NIFTY", asOf }, ctrl.signal)
        .then((d) => { setData(d); setError(null); })
        .catch((e: Error) => { if (e.name !== "AbortError") setError(e.message); });
    // Debounce so dragging the replay slider issues one request per pause.
    const first = setTimeout(load, mode.kind === "replay" ? 120 : 0);
    const timer = mode.kind === "live" ? setInterval(load, LIVE_REFRESH_MS) : undefined;
    return () => { ctrl.abort(); clearTimeout(first); clearInterval(timer); };
  }, [mode.kind, asOf]);

  const startReplay = () => {
    if (!data) return;
    setMode({ kind: "replay", day: data.session_day, bar: Math.max(0, (data.candles.length || BARS_PER_SESSION) - 1) });
  };

  return (
    <main>
      <div className="sim-banner" role="alert">
        <strong>SIMULATED</strong> data from a deterministic generator. These are not real NIFTY prices.
        No broker is connected and no orders can be placed.
      </div>

      <header className="top">
        <div>
          <h1>OptionPulse <span className="ai">AI</span></h1>
          <p className="muted">
            {data ? `${data.instrument.display_name} · ${data.instrument.exchange} · 5-minute` : "NIFTY 50 · 5-minute"}
            <span className="badge sim">SIMULATED</span>
          </p>
        </div>
        <div className="controls">
          <div className="seg" role="group" aria-label="Mode">
            <button className={mode.kind === "live" ? "on" : ""} onClick={() => setMode({ kind: "live" })}>Live clock</button>
            <button className={mode.kind === "replay" ? "on" : ""} onClick={startReplay} disabled={!data}>Replay</button>
          </div>
          {mode.kind === "replay" && data && (
            <div className="replay">
              <select value={mode.day} onChange={(e) => setMode({ ...mode, day: e.target.value })} aria-label="Session">
                {[...new Set([mode.day, ...data.sessions])].map((d) => <option key={d} value={d}>{day(d)}</option>)}
              </select>
              <input type="range" min={0} max={BARS_PER_SESSION - 1} value={mode.bar} aria-label="Replay time"
                onChange={(e) => setMode({ ...mode, bar: Number(e.target.value) })} />
              <span className="mono">{clock(barEnd(mode.day, mode.bar))}</span>
            </div>
          )}
        </div>
      </header>

      {error && (
        <div className="panel error">
          <strong>Backend unavailable.</strong> {error}
          <p className="muted">Start it with <code>uvicorn optionpulse.main:app --port 8000</code> from <code>optionpulse/backend</code>.</p>
        </div>
      )}

      {data && (
        <>
          <p className="status muted">
            Session {day(data.session_day)} · as of {clock(data.as_of)} IST ·{" "}
            {data.market_open ? <span className="open">market hours</span> : <span>market closed</span>}
            {mode.kind === "live" && ` · refreshes every ${LIVE_REFRESH_MS / 1000}s`}
          </p>
          <div className="layout">
            <section className="panel chart-panel">
              {data.candles.length === 0 ? (
                <p className="empty">Waiting for the first 5-minute candle of the session (09:15–09:20 IST).</p>
              ) : (
                <PriceChart candles={data.candles} config={data.config} />
              )}
            </section>
            <SignalPanel result={data.signal} />
          </div>
          <footer className="fine">{data.disclaimer}</footer>
        </>
      )}
      {!data && !error && <p className="muted">Loading…</p>}
    </main>
  );
}
