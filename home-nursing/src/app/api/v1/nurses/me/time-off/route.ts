import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { AppError } from "@/lib/errors";
import { nurseIdFor } from "@/lib/domain/access";

export const GET = route({ permission: "nurse.self" }, async ({ principal }) => {
  const nurseId = await nurseIdFor(prisma, principal!);
  return prisma.nurseAvailabilityException.findMany({ where: { nurseId, endsAt: { gt: new Date() } }, orderBy: { startsAt: "asc" } });
});

/** Time off / holiday / break. Does not cancel existing bookings — those must be handled explicitly. */
export const POST = route({ permission: "nurse.self", body: z.object({ startsAt: z.string().datetime(), endsAt: z.string().datetime(), reason: z.string().max(80).optional() }) }, async ({ principal, body }) => {
  const nurseId = await nurseIdFor(prisma, principal!);
  const s = new Date(body.startsAt), e = new Date(body.endsAt);
  if (e <= s) throw new AppError("VALIDATION", "End must be after start");
  const clashes = await prisma.appointment.count({ where: { nurseId, status: { in: ["CONFIRMED", "AWAITING_NURSE_ACCEPTANCE"] }, startAt: { lt: e }, endAt: { gt: s } } });
  const x = await prisma.nurseAvailabilityException.create({ data: { nurseId, startsAt: s, endsAt: e, reason: body.reason } });
  return { exception: x, existingBookingsInPeriod: clashes };
});

export const DELETE = route({ permission: "nurse.self", body: z.object({ id: z.string() }) }, async ({ principal, body }) => {
  const nurseId = await nurseIdFor(prisma, principal!);
  await prisma.nurseAvailabilityException.deleteMany({ where: { id: body.id, nurseId } });
  return { ok: true };
});
