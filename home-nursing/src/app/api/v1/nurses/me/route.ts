import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";

export const GET = route({ permission: "nurse.self" }, async ({ principal }) =>
  prisma.nurseProfile.findUnique({
    where: { userId: principal!.userId },
    include: { qualifications: true, registrations: true, documents: { select: { id: true, kind: true, status: true, expiresOn: true, uploadedAt: true, mandatory: true } }, eligibilities: { include: { service: { select: { name: true } } } }, serviceAreas: true, availability: true, exceptions: true },
  }),
);

export const PUT = route(
  {
    permission: "nurse.self",
    body: z.object({
      displayName: z.string().min(2).max(100), gender: z.enum(["FEMALE", "MALE", "OTHER", "UNDISCLOSED"]), bio: z.string().max(1000).optional(),
      languages: z.array(z.string().max(30)).min(1).max(10), yearsExperience: z.number().int().min(0).max(60),
      qualifications: z.array(z.object({ code: z.string().max(40), institution: z.string().max(120).optional(), yearCompleted: z.number().int().min(1960).max(2100).optional() })).max(10).optional(),
      serviceArea: z.object({ label: z.string().max(80), city: z.string().max(60), latitude: z.number(), longitude: z.number(), maxTravelMinutes: z.number().int().min(10).max(240).optional() }).optional(),
    }),
  },
  async ({ principal, body }) => {
    const { qualifications, serviceArea, ...profile } = body;
    return prisma.$transaction(async (tx) => {
      const n = await tx.nurseProfile.upsert({ where: { userId: principal!.userId }, create: { ...profile, userId: principal!.userId }, update: profile });
      if (qualifications) {
        // Only replace unverified rows; verified ones are an audited admin decision.
        await tx.nurseQualification.deleteMany({ where: { nurseId: n.id, verificationStatus: { not: "VERIFIED" } } });
        await tx.nurseQualification.createMany({ data: qualifications.map((q) => ({ ...q, nurseId: n.id })) });
      }
      if (serviceArea) {
        await tx.nurseServiceArea.deleteMany({ where: { nurseId: n.id } });
        await tx.nurseServiceArea.create({ data: { ...serviceArea, nurseId: n.id, isPrimary: true } });
      }
      return n;
    });
  },
);
