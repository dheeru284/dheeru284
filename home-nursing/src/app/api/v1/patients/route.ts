import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { recordConsent } from "@/lib/domain/privacy";

export const GET = route({ permission: "patient.self" }, async ({ principal }) =>
  prisma.patientProfile.findMany({
    where: { deletedAt: null, OR: [{ accountUserId: principal!.userId }, { caregivers: { some: { caregiverUserId: principal!.userId } } }] },
    orderBy: { createdAt: "asc" },
  }),
);

export const POST = route(
  {
    permission: "patient.self",
    body: z.object({
      fullName: z.string().min(2).max(100),
      dateOfBirth: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional(),
      gender: z.enum(["FEMALE", "MALE", "OTHER", "UNDISCLOSED"]).default("UNDISCLOSED"),
      medicalNotes: z.string().max(2000).optional(),
      allergies: z.string().max(500).optional(),
      emergencyContactName: z.string().max(100).optional(),
      emergencyContactPhone: z.string().max(20).optional(),
      consentToCareDataProcessing: z.literal(true, { errorMap: () => ({ message: "Consent is required to store care information" }) }),
    }),
  },
  async ({ principal, body }) => {
    const { consentToCareDataProcessing: _c, dateOfBirth, ...rest } = body;
    const p = await prisma.patientProfile.create({ data: { ...rest, accountUserId: principal!.userId, dateOfBirth: dateOfBirth ? new Date(dateOfBirth) : undefined } });
    await recordConsent(principal!, "care_delivery", p.id);
    return p;
  },
);
