export const DEFAULT_TZ = "Asia/Kolkata";

const DOW: Record<string, number> = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };

/** Wall-clock parts of an instant in a timezone. */
export function localParts(at: Date, tz = DEFAULT_TZ) {
  const f = new Intl.DateTimeFormat("en-US", {
    timeZone: tz,
    weekday: "short",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
  const p = Object.fromEntries(f.formatToParts(at).map((x) => [x.type, x.value]));
  return {
    dayOfWeek: DOW[p.weekday as string]!,
    minuteOfDay: Number(p.hour) * 60 + Number(p.minute),
    date: `${p.year}-${p.month}-${p.day}`,
  };
}

/** Convert a local wall-clock date+time in tz to a UTC instant. */
export function zonedToUtc(date: string, time: string, tz = DEFAULT_TZ): Date {
  const guess = new Date(`${date}T${time}:00Z`);
  const p = localParts(guess, tz);
  const [h, m] = time.split(":").map(Number);
  const wantMin = h! * 60 + m!;
  let diff = p.minuteOfDay - wantMin;
  if (p.date !== date) diff += p.date > date ? 1440 : -1440;
  return new Date(guess.getTime() - diff * 60_000);
}

export function formatInTz(at: Date, tz = DEFAULT_TZ) {
  return new Intl.DateTimeFormat("en-IN", { timeZone: tz, dateStyle: "medium", timeStyle: "short" }).format(at);
}

export const addMinutes = (d: Date, m: number) => new Date(d.getTime() + m * 60_000);
export const nightsBetween = (a: Date, b: Date) => Math.round((b.getTime() - a.getTime()) / 86_400_000);
