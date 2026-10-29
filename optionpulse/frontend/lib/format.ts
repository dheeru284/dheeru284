const IST = "Asia/Kolkata";

export const price = (v: number | null | undefined) =>
  v == null ? "—" : v.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const clock = (iso: string) =>
  new Date(iso).toLocaleTimeString("en-IN", { timeZone: IST, hour: "2-digit", minute: "2-digit", hour12: false });

export const day = (isoDate: string) =>
  new Date(`${isoDate}T12:00:00+05:30`).toLocaleDateString("en-IN", {
    timeZone: IST, weekday: "short", day: "2-digit", month: "short", year: "numeric",
  });

/** Session bar end (start + 5 min) for bar index i on an IST date, as an ISO string. */
export function barEnd(isoDate: string, index: number): string {
  const open = new Date(`${isoDate}T09:15:00+05:30`).getTime();
  return new Date(open + (index + 1) * 5 * 60_000).toISOString();
}

export const BARS_PER_SESSION = 75;
