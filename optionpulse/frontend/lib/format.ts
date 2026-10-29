const IST = "Asia/Kolkata";

export const price = (v: number | null | undefined, digits = 2) =>
  v == null ? "—" : v.toLocaleString("en-IN", { minimumFractionDigits: digits, maximumFractionDigits: digits });

export const signed = (v: number | null | undefined, digits = 2) =>
  v == null ? "—" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toLocaleString("en-IN", { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;

export const clock = (iso: string) =>
  new Date(iso).toLocaleTimeString("en-IN", { timeZone: IST, hour: "2-digit", minute: "2-digit", hour12: false });

export const day = (isoDate: string) =>
  new Date(`${isoDate.slice(0, 10)}T12:00:00+05:30`).toLocaleDateString("en-IN", {
    timeZone: IST, weekday: "short", day: "2-digit", month: "short",
  });

export const dateTime = (iso: string) => `${day(iso.slice(0, 10))} ${clock(iso)}`;

export function ago(iso: string | null): string {
  if (!iso) return "";
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  return hrs < 24 ? `${hrs}h ago` : `${Math.round(hrs / 24)}d ago`;
}

export function greeting(): string {
  const h = Number(new Date().toLocaleString("en-IN", { timeZone: IST, hour: "numeric", hour12: false }));
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

export const BARS_PER_SESSION = 75;

export const STRATEGY_COLORS: Record<string, string> = {
  trend_pulse: "var(--c-trend)",
  orb: "var(--c-orb)",
  vwap_snapback: "var(--c-snap)",
};

export const SOURCE_LABEL: Record<string, string> = {
  SIMULATED: "Simulated data",
  PUBLIC_DELAYED: "Live · delayed",
  BROKER_HISTORICAL: "Broker · historical",
  BROKER_LIVE: "Broker · live",
};
