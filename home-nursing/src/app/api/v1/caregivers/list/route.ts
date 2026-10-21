import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";

/** Caregiver links on profiles the user holds. */
export const GET = route({ permission: "patient.self" }, async ({ principal }) =>
  prisma.caregiverRelationship.findMany({ where: { patient: { accountUserId: principal!.userId } }, include: { patient: { select: { fullName: true } }, caregiver: { select: { fullName: true, phone: true } } } }),
);
export const DELETE = route({ permission: "patient.self", body: z.object({ id: z.string() }) }, async ({ principal, body }) => {
  await prisma.caregiverRelationship.deleteMany({ where: { id: body.id, patient: { accountUserId: principal!.userId } } });
  return { ok: true };
});
