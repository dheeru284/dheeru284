import type { NurseAvailability, NurseAvailabilityException } from "@prisma/client";
import { addMinutes, localParts } from "../time";

export type Busy = { blockStart: Date; blockEnd: Date };

export function blockWindow(startAt: Date, durationMinutes: number, s: { travelBufferMinutes: number; appointmentBufferMinutes: number }) {
  const endAt = addMinutes(startAt, durationMinutes);
  return { endAt, blockStart: addMinutes(startAt, -s.travelBufferMinutes), blockEnd: addMinutes(endAt, s.appointmentBufferMinutes) };
}

/** Does [startAt, endAt) fall inside one weekly working window on the local day, avoiding exceptions and existing bookings? */
export function isAvailable(
  startAt: Date,
  endAt: Date,
  block: Busy,
  weekly: NurseAvailability[],
  exceptions: Pick<NurseAvailabilityException, "startsAt" | "endsAt">[],
  busy: Busy[],
): { ok: boolean; reason?: string } {
  const tz = weekly[0]?.timezone ?? "Asia/Kolkata";
  const s = localParts(startAt, tz);
  const e = localParts(endAt, tz);
  if (s.date !== e.date && e.minuteOfDay !== 0) return { ok: false, reason: "spans_midnight" };
  const endMin = e.minuteOfDay === 0 && s.date !== e.date ? 1440 : e.minuteOfDay;
  const fits = weekly.some((w) => w.dayOfWeek === s.dayOfWeek && w.startMinute <= s.minuteOfDay && endMin <= w.endMinute);
  if (!fits) return { ok: false, reason: "outside_working_hours" };
  const overlaps = (a0: Date, a1: Date, b0: Date, b1: Date) => a0 < b1 && b0 < a1;
  if (exceptions.some((x) => overlaps(startAt, endAt, x.startsAt, x.endsAt))) return { ok: false, reason: "time_off" };
  if (busy.some((b) => overlaps(block.blockStart, block.blockEnd, b.blockStart, b.blockEnd))) return { ok: false, reason: "already_booked" };
  return { ok: true };
}
