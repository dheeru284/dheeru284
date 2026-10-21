import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { AppError } from "@/lib/errors";
import { assertPatientAccess } from "@/lib/domain/access";

export const POST = route({ permission: "review.write", body: z.object({ rating: z.number().int().min(1).max(5), comment: z.string().max(1000).optional() }) }, async ({ principal, params, body }) => {
  const a = await prisma.appointment.findUnique({ where: { id: params.id! } });
  if (!a) throw new AppError("NOT_FOUND", "Appointment not found");
  await assertPatientAccess(prisma, principal!, a.patientId);
  if (a.status !== "COMPLETED") throw new AppError("PRECONDITION_FAILED", "You can review only completed visits");
  return prisma.$transaction(async (tx) => {
    const r = await tx.review.create({ data: { appointmentId: a.id, nurseId: a.nurseId, rating: body.rating, comment: body.comment } });
    const agg = await tx.review.aggregate({ where: { nurseId: a.nurseId, moderationStatus: "VISIBLE" }, _avg: { rating: true }, _count: true });
    await tx.nurseProfile.update({ where: { id: a.nurseId }, data: { ratingAvg: agg._avg.rating ?? 0, ratingCount: agg._count } });
    return r;
  });
});
