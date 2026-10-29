// Mirrors optionpulse.api.Dashboard and optionpulse.strategy.StrategyResult.

export type DataSource = "SIMULATED" | "BROKER_HISTORICAL" | "BROKER_LIVE";
export type Signal = "LONG_SETUP" | "SHORT_SETUP" | "NO_TRADE" | "DATA_INVALID";

export interface Instrument {
  symbol: string;
  display_name: string;
  exchange: string;
  instrument_type: string;
  tick_size: number;
  lot_size: number;
}

export interface DashboardCandle {
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

export interface Check {
  name: string;
  passed: boolean;
  detail: string;
}

export interface DataIssue {
  code: string;
  message: string;
  timestamp: string | null;
}

export interface StrategyResult {
  signal: Signal;
  symbol: string;
  interval: string;
  source: DataSource;
  evaluated_candle: string | null;
  reasons: string[];
  long_checks: Check[];
  short_checks: Check[];
  indicators: { close: number; ema_fast: number; ema_slow: number; vwap: number; rsi: number } | null;
  issues: DataIssue[];
}

export interface StrategyConfig {
  ema_fast: number;
  ema_slow: number;
  rsi_period: number;
  long_rsi_min: number;
  long_rsi_max: number;
  short_rsi_min: number;
  short_rsi_max: number;
}

export interface Dashboard {
  instrument: Instrument;
  interval: string;
  source: DataSource;
  simulated: boolean;
  as_of: string;
  market_open: boolean;
  session_day: string;
  sessions: string[];
  candles: DashboardCandle[];
  signal: StrategyResult;
  config: StrategyConfig;
  disclaimer: string;
}
