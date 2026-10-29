"use client";

import Link from "next/link";
import { fetchOverview } from "@/lib/api";
import { STRATEGY_COLORS, ago, clock, day, greeting, price, signed } from "@/lib/format";
import type { FactorSnapshot, LiveStrategy, NewsDigest, Overview } from "@/lib/types";
import { usePolling } from "@/lib/useWidth";
import { PriceChart, Sparkline } from "./charts";
import { Checks, Dot, ErrorCard, RegimeBadge, SourceNotes, StateBadge } from "./ui";

const REFRESH_MS = 30_000;

export function OverviewView() {
  const { data, error, loading } = usePolling<Overview>(fetchOverview, REFRESH_MS);

  if (!data) {
    return error ? <ErrorCard message={error} /> : <p className="muted loading">{loading ? "Gathering today's market…" : ""}</p>;
  }
  const first = data.candles[0];
  const last = data.candles[data.candles.length - 1];
  const sinceOpen = first && last ? last.close - first.open : null;
  const deskPoints = data.strategies.reduce((sum, s) => sum + s.today_points, 0);
  const trades = data.strategies.flatMap((s) => s.today_trades);

  return (
    <>
      <section className="hero">
        <div>
          <p className="eyebrow">{greeting()} · {day(data.session_day)}</p>
          <h1>
            {data.display_name}{" "}
            <span className="hero-price">{price(last?.close)}</span>{" "}
            {sinceOpen != null && (
              <span className={`delta ${sinceOpen >= 0 ? "good" : "bad"}`}>{signed(sinceOpen)} since open</span>
            )}
          </h1>
          <p className="muted">
            {data.market_open ? <span className="open-dot">Market open</span> : "Market closed"} · updated{" "}
            {clock(data.as_of)} IST · refreshes every {REFRESH_MS / 1000}s
            {error && <span className="bad"> · last refresh failed, showing the previous update</span>}
          </p>
        </div>
        <div className="hero-cards">
          <div className="mini-card">
            <span className="kpi-label">Paper desk today</span>
            <span className={`kpi-value ${deskPoints > 0 ? "good" : deskPoints < 0 ? "bad" : ""}`}>{signed(deskPoints)} pts</span>
            <span className="muted small">{trades.length} trade{trades.length === 1 ? "" : "s"} across {data.strategies.length} strategies</span>
          </div>
          <div className="mini-card">
            <span className="kpi-label">Market mood</span>
            <RegimeBadge regime={data.macro.regime.regime} />
            <span className="muted small">{data.macro.regime.reasons[0]}</span>
          </div>
        </div>
      </section>

      <SourceNotes source={data.source} notes={data.notes} />
      {data.data_issues.length > 0 && (
        <div className="notice warn">
          <strong>Today&apos;s data has problems, so no new paper trades are taken</strong>
          <ul>{data.data_issues.slice(0, 4).map((i) => <li key={i.code + i.timestamp}>{i.code}: {i.message}</li>)}</ul>
        </div>
      )}

      <div className="grid-main">
        <section className="card">
          <div className="card-head">
            <h2>Today&apos;s chart</h2>
            <span className="muted small">5-minute candles · markers are today&apos;s paper trades</span>
          </div>
          {data.candles.length ? (
            <PriceChart candles={data.candles} trades={trades}
              watermark={data.source === "SIMULATED" ? "SIMULATED" : undefined} />
          ) : (
            <p className="empty-chart">The first 5-minute candle closes at 09:20 IST.</p>
          )}
        </section>

        <section className="card desk">
          <div className="card-head">
            <h2>Paper desk</h2>
            <Link href="/strategies" className="link small">How they work →</Link>
          </div>
          {data.strategies.map((s) => <DeskRow key={s.info.id} s={s} lastClose={last?.close} />)}
          {trades.length > 0 && (
            <>
              <h4>Today&apos;s trades</h4>
              <ul className="desk-trades">
                {[...trades].sort((a, b) => (a.entry_time < b.entry_time ? 1 : -1)).map((t) => (
                  <li key={t.id}>
                    <span className="muted">{clock(t.entry_time)}</span>
                    <span><Dot id={t.strategy_id} /><span className={`side ${t.side.toLowerCase()}`}>{t.side === "LONG" ? "Long" : "Short"}</span></span>
                    <span className={`chip reason-${t.exit_reason.toLowerCase()}`}>{t.exit_reason === "SQUARE_OFF" ? "15:20 exit" : t.exit_reason[0] + t.exit_reason.slice(1).toLowerCase()}</span>
                    <span className={`pts ${t.points > 0 ? "good" : t.points < 0 ? "bad" : ""}`}>{signed(t.points)}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
          <p className="muted small">
            {data.live_filter ? "Trading with the market-mood filter on." : "Market-mood filter off."} Points are NIFTY index points after slippage.
          </p>
        </section>
      </div>

      <section className="card">
        <div className="card-head">
          <h2>What else is moving</h2>
          <span className="muted small">Change since yesterday · hover a tile for why it matters</span>
        </div>
        <div className="factors">
          {data.macro.factors.map((f) => <FactorTile key={f.key} f={f} />)}
        </div>
        <div className="regime-line">
          <RegimeBadge regime={data.macro.regime.regime} />
          <span>{data.macro.regime.reasons.join(" · ")}</span>
          <Link href="/strategies#filter" className="link small">How mood is used →</Link>
        </div>
      </section>

      <NewsCard news={data.news} />
      {trades.length > 0 && (
        <p className="muted small center">
          Want the full history? <Link href="/performance" className="link">See how each strategy has performed →</Link>
        </p>
      )}
    </>
  );
}

function DeskRow({ s, lastClose }: { s: LiveStrategy; lastClose?: number }) {
  const pos = s.position;
  return (
    <details className="desk-row" style={{ borderLeftColor: STRATEGY_COLORS[s.info.id] }}>
      <summary>
        <span className="desk-name"><Dot id={s.info.id} />{s.info.name}</span>
        <StateBadge state={s.state} />
        <span className={`desk-pts ${s.today_points > 0 ? "good" : s.today_points < 0 ? "bad" : "muted"}`}>
          {signed(s.today_points)}
        </span>
      </summary>
      <div className="desk-body">
        {pos ? (
          <p className="position">
            <strong>{pos.side === "LONG" ? "Long" : "Short"}</strong> since {clock(pos.entry_time)} at {price(pos.entry_price)} ·
            stop {price(pos.stop)} · target {price(pos.target)} · now{" "}
            <span className={pos.points >= 0 ? "good" : "bad"}>{signed(pos.points)} pts</span>
            {lastClose != null && <span className="muted"> (last {price(lastClose)})</span>}
          </p>
        ) : (
          <p className="muted small">No open position.{s.today_trades.length ? ` ${s.today_trades.length} closed today.` : ""}</p>
        )}
        {s.skipped_today > 0 && <p className="muted small">{s.skipped_today} setup{s.skipped_today > 1 ? "s" : ""} skipped today by the mood filter.</p>}
        {s.setup?.note && <p className="muted small">{s.setup.note}</p>}
        {s.setup && s.setup.long_checks.length > 0 && (
          <div className="two-col">
            <div><h4>Long checks</h4><Checks checks={s.setup.long_checks} /></div>
            <div><h4>Short checks</h4><Checks checks={s.setup.short_checks} /></div>
          </div>
        )}
      </div>
    </details>
  );
}

function FactorTile({ f }: { f: FactorSnapshot }) {
  const chg = f.change_pct;
  // Tone is about NIFTY: oil rising is "bad", S&P rising is "good".
  let tone: "good" | "bad" | "flat" = "flat";
  if (chg != null && Math.abs(chg) >= 0.05 && f.risk_off_when_rising != null) {
    const rising = chg > 0;
    tone = rising === f.risk_off_when_rising ? "bad" : "good";
  }
  return (
    <div className={`factor ${tone}`} title={f.why}>
      <div className="factor-top">
        <span className="factor-label">{f.label}</span>
        <span className={`factor-chg ${tone}`}>{chg == null ? "—" : `${signed(chg)}%`}</span>
      </div>
      <span className="factor-value">{f.value == null ? "—" : price(f.value, f.value < 10 ? 3 : 2)} <small>{f.unit}</small></span>
      {f.error ? <span className="muted small">unavailable</span> : <Sparkline values={f.sparkline} rising={tone} />}
    </div>
  );
}

function NewsCard({ news }: { news: NewsDigest }) {
  const mood = news.mood;
  const pct = mood == null ? 50 : Math.round((mood + 1) * 50);
  return (
    <section className="card">
      <div className="card-head">
        <h2>Headlines</h2>
        <span className="muted small">Fetched {ago(news.fetched_at)} · keyword scoring, shown for context only</span>
      </div>
      {news.items.length > 0 ? (
        <>
          <div className="mood">
            <span className="small muted">Headline mood</span>
            <div className="mood-bar" role="meter" aria-valuemin={-1} aria-valuemax={1} aria-valuenow={mood ?? 0}>
              <span className="mood-marker" style={{ left: `${pct}%` }} />
            </div>
            <span className="small">
              <span className="good">{news.positive} upbeat</span> · <span className="bad">{news.negative} worried</span> · {news.neutral} neutral
            </span>
          </div>
          <ul className="news">
            {news.items.slice(0, 14).map((n) => (
              <li key={n.link || n.title}>
                <span className={`tone ${n.label.toLowerCase()}`} aria-label={n.label.toLowerCase()} />
                <div>
                  <a href={n.link} target="_blank" rel="noreferrer noopener">{n.title}</a>
                  <div className="news-meta">
                    {n.source} · {ago(n.published)}
                    {n.topics.map((t) => <span key={t} className="chip soft">{t}</span>)}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="muted">No headlines right now.{news.errors.length ? " The news feeds could not be reached:" : ""}</p>
      )}
      {news.errors.length > 0 && (
        <details className="small muted"><summary>{news.errors.length} feed{news.errors.length > 1 ? "s" : ""} unavailable</summary>
          <ul>{news.errors.map((e) => <li key={e}>{e}</li>)}</ul></details>
      )}
    </section>
  );
}
