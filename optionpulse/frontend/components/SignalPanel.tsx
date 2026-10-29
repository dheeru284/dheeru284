import type { Check, StrategyResult } from "@/lib/types";
import { clock, price } from "@/lib/format";

const LABEL: Record<StrategyResult["signal"], string> = {
  LONG_SETUP: "Long setup",
  SHORT_SETUP: "Short setup",
  NO_TRADE: "No trade",
  DATA_INVALID: "Data invalid",
};

function Checks({ title, checks }: { title: string; checks: Check[] }) {
  return (
    <div className="checks">
      <h3>{title}</h3>
      <ul>
        {checks.map((c) => (
          <li key={c.name} className={c.passed ? "pass" : "fail"}>
            <span className="mark" aria-label={c.passed ? "passed" : "failed"}>{c.passed ? "✓" : "✗"}</span>
            <span className="name">{c.name}</span>
            <span className="detail">{c.detail}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function SignalPanel({ result }: { result: StrategyResult }) {
  const ind = result.indicators;
  return (
    <section className="panel signal-panel">
      <div className={`signal ${result.signal.toLowerCase()}`}>
        <span className="signal-code">{result.signal}</span>
        <span className="signal-label">{LABEL[result.signal]}</span>
      </div>
      <p className="muted">
        {result.evaluated_candle ? `Candle ${clock(result.evaluated_candle)} IST (last closed bar)` : "No closed candle yet"}
        {" · "}source {result.source}
      </p>
      <ul className="reasons">
        {result.reasons.map((r) => <li key={r}>{r}</li>)}
      </ul>

      {ind && (
        <dl className="tiles">
          <div><dt>Close</dt><dd>{price(ind.close)}</dd></div>
          <div><dt>EMA 9</dt><dd className="ema-fast">{price(ind.ema_fast)}</dd></div>
          <div><dt>EMA 21</dt><dd className="ema-slow">{price(ind.ema_slow)}</dd></div>
          <div><dt>VWAP</dt><dd className="vwap">{price(ind.vwap)}</dd></div>
          <div><dt>RSI 14</dt><dd className="rsi">{ind.rsi.toFixed(1)}</dd></div>
        </dl>
      )}

      {result.long_checks.length > 0 && (
        <div className="check-grid">
          <Checks title="Long conditions" checks={result.long_checks} />
          <Checks title="Short conditions" checks={result.short_checks} />
        </div>
      )}
      <p className="fine">A setup describes the last candle against fixed rules. It is not advice and no order is placed.</p>
    </section>
  );
}
