import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { nurseIdFor } from "@/lib/domain/access";

export const POST = route(
  { permission: "nurse.self", body: z.object({ councilName: z.string().min(3).max(120), state: z.string().max(60), registrationNumber: z.string().min(2).max(40), issuedOn: z.string().optional(), expiresOn: z.string().optional() }) },
  async ({ principal, body }) => {
    const nurseId = await nurseIdFor(prisma, principal!);
    return prisma.nurseRegistration.create({ data: { ...body, nurseId, issuedOn: body.issuedOn ? new Date(body.issuedOn) : null, expiresOn: body.expiresOn ? new Date(body.expiresOn) : null, status: "PENDING" } });
  },
);
