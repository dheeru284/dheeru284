"use client";

import { useEffect, useMemo, useState } from "react";
import { fetchPerformance } from "@/lib/api";
import { STRATEGY_COLORS, day, signed } from "@/lib/format";
import type { Performance, Stats, StrategyRun, Trade } from "@/lib/types";
import { usePolling } from "@/lib/useWidth";
import { EquityChart, type EquitySeries } from "./charts";
import { Dot, ErrorCard, Kpi, SourceNotes, TradesTable } from "./ui";

type FilterMode = "on" | "off" | "compare";
const SESSION_CHOICES = [5, 10, 20, 40];

function Seg<T extends string | number>({ value, options, onChange, label }: {
  value: T; options: [T, string][]; onChange: (v: T) => void; label: string;
}) {
  return (
    <div className="seg" role="group" aria-label={label}>
      {options.map(([v, text]) => (
        <button key={String(v)} className={v === value ? "on" : ""} onClick={() => onChange(v)}>{text}</button>
      ))}
    </div>
  );
}

function summarise(trades: Trade[]): Stats {
  const closed = trades.filter((t) => t.exit_reason !== "OPEN");
  const wins = closed.filter((t) => t.points > 0);
  const total = closed.reduce((s, t) => s + t.points, 0);
  const gw = wins.reduce((s, t) => s + t.points, 0);
  const gl = -closed.filter((t) => t.points <= 0).reduce((s, t) => s + t.points, 0);
  let cum = 0, peak = 0, dd = 0;
  for (const t of [...closed].sort((a, b) => (a.exit_time! < b.exit_time! ? -1 : 1))) {
    cum += t.points; peak = Math.max(peak, cum); dd = Math.max(dd, peak - cum);
  }
  return {
    trades: closed.length, open_trades: trades.length - closed.length, wins: wins.length, losses: closed.length - wins.length,
    win_rate: closed.length ? Math.round((wins.length / closed.length) * 1000) / 10 : null,
    total_points: total, avg_points: closed.length ? total / closed.length : null,
    avg_r: closed.length ? closed.reduce((s, t) => s + t.r_multiple, 0) / closed.length : null,
    profit_factor: gl > 0 ? gw / gl : null, max_drawdown: dd,
    best: closed.length ? Math.max(...closed.map((t) => t.points)) : null,
    worst: closed.length ? Math.min(...closed.map((t) => t.points)) : null,
    skipped_by_filter: 0,
  };
}

function equityOf(trades: Trade[]) {
  let cum = 0;
  return trades.filter((t) => t.exit_time).sort((a, b) => (a.exit_time! < b.exit_time! ? -1 : 1))
    .map((t) => ({ time: t.exit_time!, points: (cum += t.points) }));
}

export function PerformanceView() {
  const [sessions, setSessions] = useState(20);
  const [strategy, setStrategy] = useState("all");
  const [mode, setMode] = useState<FilterMode>("on");
  const [side, setSide] = useState<"all" | "LONG" | "SHORT">("all");
  const [outcome, setOutcome] = useState<"all" | "win" | "loss">("all");
  useEffect(() => {
    const s = new URLSearchParams(window.location.search).get("strategy");
    if (s) setStrategy(s);
  }, []);

  const { data, error, loading } = usePolling<Performance>((sig) => fetchPerformance(sessions, sig), 120_000, [sessions]);

  const view = useMemo(() => {
    if (!data) return null;
    const names = Object.fromEntries(data.strategies.map((s) => [s.id, s.name]));
    const filterOn = mode !== "off";
    const keep = (t: Trade) =>
      (side === "all" || t.side === side) &&
      (outcome === "all" || (t.exit_reason !== "OPEN" && (outcome === "win" ? t.points > 0 : t.points <= 0)));
    const runsFor = (on: boolean) => data.runs.filter((r) => r.filter_on === on && (strategy === "all" || r.strategy_id === strategy));
    const trades = runsFor(filterOn).flatMap((r) => r.trades).filter(keep);
    const skipped = runsFor(filterOn).reduce((s, r) => s + r.stats.skipped_by_filter, 0);

    let series: EquitySeries[];
    if (mode === "compare") {
      const ids = strategy === "all" ? data.strategies.map((s) => s.id) : [strategy];
      series = ids.flatMap((id) => [true, false].map((on) => ({
        id: `${id}-${on}`, label: `${names[id]} · filter ${on ? "on" : "off"}`, color: STRATEGY_COLORS[id], dashed: !on,
        points: equityOf(data.runs.find((r) => r.strategy_id === id && r.filter_on === on)!.trades.filter(keep)),
      })));
    } else {
      series = runsFor(filterOn).map((r) => ({
        id: r.strategy_id, label: names[r.strategy_id], color: STRATEGY_COLORS[r.strategy_id], points: equityOf(r.trades.filter(keep)),
      }));
      if (strategy === "all" && series.length > 1) {
        series.push({ id: "desk", label: "Whole desk", color: "var(--ink)", points: equityOf(trades) });
      }
    }
    return { names, trades, stats: { ...summarise(trades), skipped_by_filter: skipped }, series };
  }, [data, strategy, mode, side, outcome]);

  if (!data || !view) return error ? <ErrorCard message={error} /> : <p className="muted loading">Replaying the paper desk…</p>;
  const st = view.stats;

  return (
    <>
      <section className="hero slim">
        <div>
          <p className="eyebrow">Paper results · {day(data.sessions[0])} – {day(data.sessions[data.sessions.length - 1])}</p>
          <h1>How the strategies have done</h1>
          <p className="muted lead">
            Every trade below was simulated candle by candle on {data.source === "SIMULATED" ? "simulated" : "real (delayed)"} NIFTY
            prices, entering only on information available at the time. {loading && "Refreshing…"}
          </p>
        </div>
      </section>

      <SourceNotes source={data.source} notes={data.notes} />

      <div className="controls card">
        <label>Window <Seg label="Sessions" value={sessions} onChange={setSessions}
          options={SESSION_CHOICES.map((n) => [n, `${n}d`] as [number, string])} /></label>
        <label>Strategy
          <select value={strategy} onChange={(e) => setStrategy(e.target.value)}>
            <option value="all">All strategies</option>
            {data.strategies.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </label>
        <label>Mood filter <Seg label="Mood filter" value={mode} onChange={setMode}
          options={[["on", "On"], ["off", "Off"], ["compare", "Compare"]]} /></label>
        <label>Side <Seg label="Side" value={side} onChange={setSide} options={[["all", "Both"], ["LONG", "Long"], ["SHORT", "Short"]]} /></label>
        <label>Outcome <Seg label="Outcome" value={outcome} onChange={setOutcome} options={[["all", "All"], ["win", "Wins"], ["loss", "Losses"]]} /></label>
      </div>

      <div className="kpis">
        <Kpi label="Net points" value={signed(st.total_points, 1)} tone={st.total_points >= 0 ? "good" : "bad"} hint="Sum of closed trades after slippage" />
        <Kpi label="Trades" value={String(st.trades)} hint={st.open_trades ? `${st.open_trades} still open` : undefined} />
        <Kpi label="Win rate" value={st.win_rate == null ? "—" : `${st.win_rate}%`} />
        <Kpi label="Profit factor" value={st.profit_factor == null ? "—" : st.profit_factor.toFixed(2)} hint="Gross wins ÷ gross losses. Above 1 means it made money." />
        <Kpi label="Avg R" value={signed(st.avg_r)} hint="Average result in units of the risk taken" />
        <Kpi label="Max drawdown" value={`${st.max_drawdown.toFixed(1)} pts`} hint="Largest peak-to-trough drop in cumulative points" />
        {mode !== "off" && <Kpi label="Skipped by mood" value={String(st.skipped_by_filter)} />}
      </div>

      <section className="card">
        <div className="card-head">
          <h2>Cumulative points</h2>
          <span className="muted small">{mode === "compare" ? "Solid: filter on · dashed: filter off" : "One line per strategy"}</span>
        </div>
        <EquityChart series={view.series} />
        <div className="legend-row">
          {view.series.map((s) => <span key={s.id} className="legend-item"><i style={{ background: s.color, opacity: s.dashed ? 0.5 : 1 }} />{s.label}</span>)}
        </div>
      </section>

      <section className="card">
        <h2>Side by side</h2>
        <div className="table-wrap">
          <table className="compare">
            <thead>
              <tr><th>Strategy</th><th>Filter</th><th className="num">Trades</th><th className="num">Win %</th>
                <th className="num">Points</th><th className="num">Profit factor</th><th className="num">Avg R</th>
                <th className="num">Max DD</th><th className="num">Skipped</th></tr>
            </thead>
            <tbody>
              {data.strategies.flatMap((s) => [false, true].map((on) => {
                const r = data.runs.find((x) => x.strategy_id === s.id && x.filter_on === on) as StrategyRun;
                const k = r.stats;
                return (
                  <tr key={`${s.id}-${on}`} className={on ? "" : "sub"}>
                    <td>{on ? null : <><Dot id={s.id} />{s.name}</>}</td>
                    <td>{on ? "On" : "Off"}</td>
                    <td className="num">{k.trades}</td>
                    <td className="num">{k.win_rate ?? "—"}</td>
                    <td className={`num strong ${k.total_points >= 0 ? "good" : "bad"}`}>{signed(k.total_points, 1)}</td>
                    <td className="num">{k.profit_factor?.toFixed(2) ?? "—"}</td>
                    <td className="num">{signed(k.avg_r)}</td>
                    <td className="num">{k.max_drawdown.toFixed(1)}</td>
                    <td className="num">{on ? k.skipped_by_filter : "—"}</td>
                  </tr>
                );
              }))}
            </tbody>
          </table>
        </div>
        {data.skipped_sessions.length > 0 && (
          <p className="muted small">Not traded because their data failed validation: {data.skipped_sessions.map(day).join(", ")}.</p>
        )}
        {data.source === "SIMULATED" && (
          <p className="muted small">On simulated (random-walk) prices no rule has a real edge, so losses after slippage are the expected result.</p>
        )}
      </section>

      <section className="card">
        <div className="card-head">
          <h2>Trade log</h2>
          <span className="muted small">{view.trades.length} trades · click a column to sort · hover a mood badge for its reasons</span>
        </div>
        <TradesTable trades={view.trades} names={view.names} showStrategy={strategy === "all"} />
      </section>

      <section className="card">
        <h2>Fine print</h2>
        <ul className="muted small">
          {data.engine_rules.map((r) => <li key={r}>{r}</li>)}
          <li>Past paper results, especially over a few weeks, say little about the future.</li>
        </ul>
      </section>
    </>
  );
}
