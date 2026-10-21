import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { AppError } from "@/lib/errors";
import { mergeHospitals, updateHospital } from "@/lib/domain/admin";

export const GET = route({}, async ({ params }) => {
  const h = await prisma.hospital.findFirst({ where: { id: params.id!, isActive: true } });
  if (!h) throw new AppError("NOT_FOUND", "Hospital not found");
  return h;
});

export const PATCH = route(
  {
    permission: "hospital.manage",
    body: z.object({
      name: z.string().min(2).optional(), address: z.string().optional(), city: z.string().optional(), state: z.string().optional(), pincode: z.string().regex(/^[1-9]\d{5}$/).optional(),
      latitude: z.number().optional(), longitude: z.number().optional(), phone: z.string().optional(), website: z.string().url().optional(), specialties: z.array(z.string()).optional(),
      verificationStatus: z.enum(["UNVERIFIED", "VERIFIED"]).optional(), dataSource: z.string().optional(), isActive: z.boolean().optional(),
      hasFormalPartnership: z.boolean().optional(), partnershipAgreementRef: z.string().optional(),
      mergeInto: z.string().optional(),
    }),
  },
  async ({ principal, params, body }) => {
    const { mergeInto, ...data } = body;
    if (mergeInto) { await mergeHospitals(principal!, params.id!, mergeInto); return { merged: true }; }
    return updateHospital(principal!, params.id!, data);
  },
);
