import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";

export const GET = route({ permission: "patient.self" }, async ({ principal }) =>
  prisma.favoriteNurse.findMany({ where: { userId: principal!.userId, nurse: { status: "APPROVED" } }, select: { nurse: { select: { id: true, displayName: true, languages: true, ratingAvg: true, ratingCount: true, serviceAreas: { select: { label: true } } } } } }),
);
export const POST = route({ permission: "patient.self", body: z.object({ nurseId: z.string() }) }, async ({ principal, body }) =>
  prisma.favoriteNurse.upsert({ where: { userId_nurseId: { userId: principal!.userId, nurseId: body.nurseId } }, create: { userId: principal!.userId, nurseId: body.nurseId }, update: {} }),
);
export const DELETE = route({ permission: "patient.self", body: z.object({ nurseId: z.string() }) }, async ({ principal, body }) => {
  await prisma.favoriteNurse.deleteMany({ where: { userId: principal!.userId, nurseId: body.nurseId } });
  return { ok: true };
});
