import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { AppError } from "@/lib/errors";
import { audit } from "@/lib/domain/audit";

/** Account holder links another registered user as caregiver for one of their patient profiles. */
export const POST = route(
  { permission: "patient.self", body: z.object({ patientId: z.string(), caregiverPhone: z.string(), relation: z.string().max(40), canBook: z.boolean().default(true), canViewRecords: z.boolean().default(false) }) },
  async ({ principal, body }) => {
    const patient = await prisma.patientProfile.findFirst({ where: { id: body.patientId, accountUserId: principal!.userId } });
    if (!patient) throw new AppError("NOT_FOUND", "Patient not found");
    const cg = await prisma.user.findUnique({ where: { phone: body.caregiverPhone } });
    if (!cg) throw new AppError("NOT_FOUND", "That person must register first");
    const link = await prisma.caregiverRelationship.upsert({
      where: { patientId_caregiverUserId: { patientId: patient.id, caregiverUserId: cg.id } },
      create: { patientId: patient.id, caregiverUserId: cg.id, relation: body.relation, canBook: body.canBook, canViewRecords: body.canViewRecords },
      update: { relation: body.relation, canBook: body.canBook, canViewRecords: body.canViewRecords },
    });
    await audit(prisma, { actorUserId: principal!.userId, action: "caregiver.link", entityType: "PatientProfile", entityId: patient.id });
    return link;
  },
);
