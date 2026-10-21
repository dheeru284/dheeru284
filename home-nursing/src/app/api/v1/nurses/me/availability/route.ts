import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { nurseIdFor } from "@/lib/domain/access";

const slot = z.object({ dayOfWeek: z.number().int().min(0).max(6), startMinute: z.number().int().min(0).max(1439), endMinute: z.number().int().min(1).max(1440) }).refine((s) => s.endMinute > s.startMinute, "End must be after start");

export const PUT = route(
  { permission: "nurse.self", body: z.object({ weekly: z.array(slot).max(28), exceptions: z.array(z.object({ startsAt: z.string().datetime(), endsAt: z.string().datetime(), reason: z.string().max(80).optional() })).max(100).optional(), isPaused: z.boolean().optional() }) },
  async ({ principal, body }) => {
    const nurseId = await nurseIdFor(prisma, principal!);
    // Existing bookings are not altered; new slots only affect future matching.
    return prisma.$transaction(async (tx) => {
      await tx.nurseAvailability.deleteMany({ where: { nurseId } });
      await tx.nurseAvailability.createMany({ data: body.weekly.map((w) => ({ ...w, nurseId })) });
      if (body.exceptions) {
        await tx.nurseAvailabilityException.deleteMany({ where: { nurseId, startsAt: { gt: new Date() } } });
        await tx.nurseAvailabilityException.createMany({ data: body.exceptions.map((e) => ({ nurseId, startsAt: new Date(e.startsAt), endsAt: new Date(e.endsAt), reason: e.reason })) });
      }
      if (body.isPaused !== undefined) await tx.nurseProfile.update({ where: { id: nurseId }, data: { isPaused: body.isPaused } });
      return { ok: true };
    });
  },
);
