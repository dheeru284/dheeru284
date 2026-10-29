// Mirrors the FastAPI models in optionpulse.portal / engine / macro / news.

export type DataSource = "SIMULATED" | "PUBLIC_DELAYED" | "BROKER_HISTORICAL" | "BROKER_LIVE";
export type Side = "LONG" | "SHORT";
export type Regime = "RISK_ON" | "NEUTRAL" | "RISK_OFF" | "UNKNOWN";
export type LiveState = "LONG_SETUP" | "SHORT_SETUP" | "WATCHING" | "NOT_READY" | "DATA_INVALID";
export type ExitReason = "TARGET" | "STOP" | "SQUARE_OFF" | "OPEN";

export interface Candle {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  ema_fast: number | null;
  ema_slow: number | null;
  vwap: number | null;
  rsi: number | null;
}

export interface Check { name: string; passed: boolean; detail: string }
export interface Setup { side: Side | null; long_checks: Check[]; short_checks: Check[]; note: string }

export interface StrategyInfo {
  id: string;
  name: string;
  style: string;
  summary: string;
  how_it_works: string[];
  long_rules: string[];
  short_rules: string[];
  exit_rules: string[];
  parameters: Record<string, string>;
  works_best: string;
  struggles: string;
  one_trade_per_side_per_day: boolean;
}

export interface Trade {
  id: string;
  strategy_id: string;
  side: Side;
  signal_time: string;
  entry_time: string;
  entry_price: number;
  stop: number;
  target: number;
  exit_time: string | null;
  exit_price: number | null;
  exit_reason: ExitReason;
  points: number;
  r_multiple: number;
  bars_held: number;
  regime: Regime;
  regime_reasons: string[];
}

export interface LiveStrategy {
  info: StrategyInfo;
  state: LiveState;
  setup: Setup | null;
  position: Trade | null;
  today_trades: Trade[];
  today_points: number;
  skipped_today: number;
}

export interface FactorSnapshot {
  key: string;
  label: string;
  unit: string;
  why: string;
  risk_off_when_rising: boolean | null;
  value: number | null;
  change_pct: number | null;
  sparkline: number[];
  error: string | null;
}

export interface RegimeReading { regime: Regime; reasons: string[]; changes: Record<string, number | null> }

export interface NewsItem {
  title: string;
  link: string;
  source: string;
  feed: string;
  published: string | null;
  score: number;
  label: "POSITIVE" | "NEGATIVE" | "NEUTRAL";
  topics: string[];
  matched: string[];
}

export interface NewsDigest {
  items: NewsItem[];
  mood: number | null;
  positive: number;
  negative: number;
  neutral: number;
  errors: string[];
  fetched_at: string;
}

export interface DataIssue { code: string; message: string; timestamp: string | null }

export interface Overview {
  symbol: string;
  display_name: string;
  source: DataSource;
  as_of: string;
  market_open: boolean;
  session_day: string;
  data_issues: DataIssue[];
  notes: string[];
  candles: Candle[];
  strategies: LiveStrategy[];
  macro: { factors: FactorSnapshot[]; regime: RegimeReading; source: DataSource; errors: string[] };
  news: NewsDigest;
  engine_rules: string[];
  live_filter: boolean;
}

export interface Stats {
  trades: number;
  open_trades: number;
  wins: number;
  losses: number;
  win_rate: number | null;
  total_points: number;
  avg_points: number | null;
  avg_r: number | null;
  profit_factor: number | null;
  max_drawdown: number;
  best: number | null;
  worst: number | null;
  skipped_by_filter: number;
}

export interface StrategyRun {
  strategy_id: string;
  filter_on: boolean;
  stats: Stats;
  equity: { time: string; points: number }[];
  trades: Trade[];
}

export interface Performance {
  symbol: string;
  source: DataSource;
  as_of: string;
  sessions: string[];
  skipped_sessions: string[];
  strategies: StrategyInfo[];
  runs: StrategyRun[];
  engine_rules: string[];
  notes: string[];
}

export interface Catalog {
  strategies: StrategyInfo[];
  engine_rules: string[];
  regime: Record<string, number>;
  factors: { key: string; label: string; why: string; risk_off_when_rising: boolean | null }[];
  live_filter: boolean;
}
