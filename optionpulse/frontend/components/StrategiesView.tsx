"use client";

import Link from "next/link";
import { fetchCatalog, fetchOverview, fetchPerformance } from "@/lib/api";
import { STRATEGY_COLORS, signed } from "@/lib/format";
import type { Catalog, Overview, Performance, StrategyInfo } from "@/lib/types";
import { usePolling } from "@/lib/useWidth";
import { Checks, ErrorCard, Kpi, StateBadge } from "./ui";

export function StrategiesView() {
  const catalog = usePolling<Catalog>(fetchCatalog, 0);
  const live = usePolling<Overview>(fetchOverview, 60_000);
  const perf = usePolling<Performance>((s) => fetchPerformance(20, s), 0);

  if (!catalog.data) return catalog.error ? <ErrorCard message={catalog.error} /> : <p className="muted loading">Loading strategies…</p>;
  const c = catalog.data;

  return (
    <>
      <section className="hero slim">
        <div>
          <p className="eyebrow">The playbook</p>
          <h1>Every strategy, in plain words</h1>
          <p className="muted lead">
            Each strategy reads finished 5-minute NIFTY candles and decides whether conditions line up. The paper desk then
            trades every one under the same rules, so you can compare them fairly.
          </p>
        </div>
      </section>

      <nav className="jump" aria-label="Strategies">
        {c.strategies.map((s) => <a key={s.id} href={`#${s.id}`} style={{ borderColor: STRATEGY_COLORS[s.id] }}>{s.name}</a>)}
        <a href="#engine">Paper desk rules</a>
        <a href="#filter">Market-mood filter</a>
      </nav>

      {c.strategies.map((s) => (
        <StrategyCard key={s.id} info={s}
          live={live.data?.strategies.find((x) => x.info.id === s.id)}
          perf={perf.data?.runs.find((r) => r.strategy_id === s.id && r.filter_on === c.live_filter)} />
      ))}

      <section className="card" id="engine">
        <h2>How a setup becomes a paper trade</h2>
        <ol className="steps">
          {c.engine_rules.map((r) => <li key={r}>{r}</li>)}
        </ol>
        <p className="muted small">
          Index points are the honest unit here: multiply by your lot size for rupees. Option premiums (theta, IV) are not
          simulated yet, so results describe the underlying move, not an options P&amp;L.
        </p>
      </section>

      <section className="card" id="filter">
        <h2>The market-mood filter</h2>
        <p>
          NIFTY doesn&apos;t trade in a vacuum. Three cross-market signals feed a simple mood reading, measured as the change
          since yesterday at the moment of each setup:
        </p>
        <div className="rule-grid">
          <div className="rule-box bad-soft">
            <h4>Risk-off when any of</h4>
            <ul>
              <li>Brent crude up {c.regime.brent_risk_off_pct}% or more</li>
              <li>India VIX up {c.regime.vix_risk_off_pct}% or more</li>
              <li>USD/INR up {c.regime.usdinr_risk_off_pct}% or more</li>
            </ul>
            <p className="small">→ long setups are skipped</p>
          </div>
          <div className="rule-box good-soft">
            <h4>Risk-on when any of</h4>
            <ul>
              <li>Brent crude down {Math.abs(c.regime.brent_risk_on_pct)}% or more</li>
              <li>India VIX down {Math.abs(c.regime.vix_risk_on_pct)}% or more</li>
              <li>USD/INR down {Math.abs(c.regime.usdinr_risk_on_pct)}% or more</li>
            </ul>
            <p className="small">→ short setups are skipped</p>
          </div>
          <div className="rule-box">
            <h4>Neutral</h4>
            <p className="small">Nothing beyond its threshold, or signals disagree. Both directions are allowed.</p>
          </div>
        </div>
        <h3>Why these factors</h3>
        <ul className="why-list">
          {c.factors.map((f) => <li key={f.key}><strong>{f.label}.</strong> {f.why}</li>)}
        </ul>
        <p className="muted small">
          Headlines are scored and shown on the Today page, but they are <strong>not</strong> used for trades: there is no
          archive of past headlines to test a news rule against, and an untested rule would only look convincing.
          The <Link href="/performance" className="link">Performance</Link> page shows every strategy with the filter on and off,
          so you can see whether it actually helps.
        </p>
      </section>
    </>
  );
}

function StrategyCard({ info, live, perf }: {
  info: StrategyInfo;
  live?: Overview["strategies"][number];
  perf?: Performance["runs"][number];
}) {
  const st = perf?.stats;
  return (
    <section className="card strategy" id={info.id} style={{ borderTopColor: STRATEGY_COLORS[info.id] }}>
      <div className="card-head">
        <div>
          <span className="chip soft">{info.style}</span>
          <h2>{info.name}</h2>
          <p className="lead">{info.summary}</p>
        </div>
        {live && <StateBadge state={live.state} />}
      </div>

      <div className="three-col">
        <div>
          <h4>How it thinks</h4>
          <ul>{info.how_it_works.map((x) => <li key={x}>{x}</li>)}</ul>
        </div>
        <div>
          <h4 className="good">Goes long when</h4>
          <ul>{info.long_rules.map((x) => <li key={x}>{x}</li>)}</ul>
          <h4 className="bad">Goes short when</h4>
          <ul>{info.short_rules.map((x) => <li key={x}>{x}</li>)}</ul>
        </div>
        <div>
          <h4>Gets out</h4>
          <ul>{info.exit_rules.map((x) => <li key={x}>{x}</li>)}</ul>
          <div className="params">
            {Object.entries(info.parameters).map(([k, v]) => <span key={k} className="chip"><b>{k}</b> {v}</span>)}
          </div>
        </div>
      </div>

      <div className="fit">
        <p><span aria-hidden>☀️</span> <strong>Shines:</strong> {info.works_best}</p>
        <p><span aria-hidden>🌧️</span> <strong>Struggles:</strong> {info.struggles}</p>
      </div>

      <div className="two-col">
        <div className="soft-box">
          <h4>Right now</h4>
          {live?.setup?.note && <p className="muted small">{live.setup.note}</p>}
          {live?.setup && live.setup.long_checks.length > 0 ? (
            <div className="two-col tight">
              <div><h5>Long</h5><Checks checks={live.setup.long_checks} /></div>
              <div><h5>Short</h5><Checks checks={live.setup.short_checks} /></div>
            </div>
          ) : (
            <p className="muted small">{live ? "Not evaluating at the moment." : "Loading live status…"}</p>
          )}
        </div>
        <div className="soft-box">
          <h4>Last 20 sessions (paper)</h4>
          {st ? (
            <div className="kpis compact">
              <Kpi label="Trades" value={String(st.trades)} />
              <Kpi label="Win rate" value={st.win_rate == null ? "—" : `${st.win_rate}%`} />
              <Kpi label="Points" value={signed(st.total_points, 1)} tone={st.total_points >= 0 ? "good" : "bad"} />
              <Kpi label="Avg R" value={signed(st.avg_r)} />
            </div>
          ) : <p className="muted small">Crunching…</p>}
          <Link href={`/performance?strategy=${info.id}`} className="link small">See every trade →</Link>
        </div>
      </div>
    </section>
  );
}
