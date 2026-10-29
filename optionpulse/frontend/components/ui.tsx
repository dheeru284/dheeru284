"use client";

import { useMemo, useState } from "react";
import type { Check, DataSource, LiveState, Regime, Trade } from "@/lib/types";
import { STRATEGY_COLORS, dateTime, price, signed } from "@/lib/format";

export function Dot({ id }: { id: string }) {
  return <span className="dot" style={{ background: STRATEGY_COLORS[id] ?? "var(--muted)" }} aria-hidden />;
}

const STATE_TEXT: Record<LiveState, string> = {
  LONG_SETUP: "Long setup",
  SHORT_SETUP: "Short setup",
  WATCHING: "Watching",
  NOT_READY: "Waiting",
  DATA_INVALID: "Data problem",
};

export function StateBadge({ state }: { state: LiveState }) {
  return <span className={`badge state-${state.toLowerCase()}`}>{STATE_TEXT[state]}</span>;
}

const REGIME_TEXT: Record<Regime, string> = {
  RISK_ON: "Risk-on",
  NEUTRAL: "Neutral",
  RISK_OFF: "Risk-off",
  UNKNOWN: "Unknown",
};

export function RegimeBadge({ regime }: { regime: Regime }) {
  return <span className={`badge regime-${regime.toLowerCase()}`}>{REGIME_TEXT[regime]}</span>;
}

export function SourceNotes({ source, notes }: { source: DataSource; notes: string[] }) {
  if (!notes.length) return null;
  return (
    <div className={`notice ${source === "SIMULATED" ? "warn" : "info"}`} role={source === "SIMULATED" ? "alert" : "note"}>
      <strong>{source === "SIMULATED" ? "Simulated data" : "About this data"}</strong>
      <ul>{notes.map((n) => <li key={n}>{n}</li>)}</ul>
    </div>
  );
}

export function Checks({ checks }: { checks: Check[] }) {
  return (
    <ul className="checks">
      {checks.map((c) => (
        <li key={c.name} className={c.passed ? "pass" : "fail"}>
          <span className="mark" aria-label={c.passed ? "passed" : "not met"}>{c.passed ? "✓" : "·"}</span>
          <span className="name">{c.name.replace("_", " ")}</span>
          <span className="detail">{c.detail}</span>
        </li>
      ))}
    </ul>
  );
}

export function Kpi({ label, value, tone, hint }: { label: string; value: string; tone?: "good" | "bad"; hint?: string }) {
  return (
    <div className="kpi" title={hint}>
      <span className="kpi-label">{label}</span>
      <span className={`kpi-value ${tone ?? ""}`}>{value}</span>
    </div>
  );
}

export function ErrorCard({ message }: { message: string }) {
  return (
    <div className="card error-card">
      <h3>We couldn&apos;t load market data</h3>
      <p>{message}</p>
      <p className="muted small">
        The backend fetches prices from Yahoo Finance. If you&apos;re offline or the feed is rate-limiting, start the
        backend with <code>OPTIONPULSE_PROVIDER=mock</code> to explore with simulated data.
      </p>
    </div>
  );
}

const REASON_TEXT: Record<string, string> = { TARGET: "Target", STOP: "Stop", SQUARE_OFF: "15:20 exit", OPEN: "Open" };

type SortKey = "entry_time" | "points" | "r_multiple";

export function TradesTable({ trades, names, showStrategy = true }: { trades: Trade[]; names: Record<string, string>; showStrategy?: boolean }) {
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: "entry_time", desc: true });
  const [page, setPage] = useState(0);
  const sorted = useMemo(() => {
    const out = [...trades].sort((a, b) => {
      const av = a[sort.key], bv = b[sort.key];
      return (av < bv ? -1 : av > bv ? 1 : 0) * (sort.desc ? -1 : 1);
    });
    return out;
  }, [trades, sort]);
  const PAGE = 25;
  const pages = Math.max(1, Math.ceil(sorted.length / PAGE));
  const rows = sorted.slice(page * PAGE, page * PAGE + PAGE);
  const head = (key: SortKey, label: string) => (
    <th>
      <button className="sort" onClick={() => { setSort((s) => ({ key, desc: s.key === key ? !s.desc : true })); setPage(0); }}>
        {label}{sort.key === key ? (sort.desc ? " ↓" : " ↑") : ""}
      </button>
    </th>
  );
  if (!trades.length) return <p className="muted empty-row">No trades match these filters.</p>;
  return (
    <div className="table-wrap">
      <table className="trades">
        <thead>
          <tr>
            {head("entry_time", "Entry")}
            {showStrategy && <th>Strategy</th>}
            <th>Side</th>
            <th className="num">Entry</th>
            <th className="num">Stop / Target</th>
            <th className="num">Exit</th>
            <th>Outcome</th>
            {head("points", "Points")}
            {head("r_multiple", "R")}
            <th>Regime</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((t) => (
            <tr key={t.id}>
              <td className="nowrap">{dateTime(t.entry_time)}</td>
              {showStrategy && <td className="nowrap"><Dot id={t.strategy_id} />{names[t.strategy_id] ?? t.strategy_id}</td>}
              <td><span className={`side ${t.side.toLowerCase()}`}>{t.side === "LONG" ? "Long" : "Short"}</span></td>
              <td className="num">{price(t.entry_price)}</td>
              <td className="num muted">{price(t.stop)} / {price(t.target)}</td>
              <td className="num">{price(t.exit_price)}</td>
              <td><span className={`chip reason-${t.exit_reason.toLowerCase()}`}>{REASON_TEXT[t.exit_reason]}</span></td>
              <td className={`num strong ${t.points > 0 ? "good" : t.points < 0 ? "bad" : ""}`}>{signed(t.points)}</td>
              <td className="num">{signed(t.r_multiple)}</td>
              <td title={t.regime_reasons.join("; ")}><RegimeBadge regime={t.regime} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      {pages > 1 && (
        <div className="pager">
          <button disabled={page === 0} onClick={() => setPage(page - 1)}>← Prev</button>
          <span className="muted">Page {page + 1} of {pages} · {trades.length} trades</span>
          <button disabled={page >= pages - 1} onClick={() => setPage(page + 1)}>Next →</button>
        </div>
      )}
    </div>
  );
}
