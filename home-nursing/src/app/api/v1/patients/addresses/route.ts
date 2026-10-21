import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";

export const GET = route({ permission: "authenticated" }, async ({ principal }) => prisma.patientAddress.findMany({ where: { userId: principal!.userId, deletedAt: null } }));

export const POST = route(
  {
    permission: "authenticated",
    body: z.object({
      label: z.string().max(40).optional(),
      line1: z.string().min(3).max(200),
      building: z.string().max(100).optional(),
      landmark: z.string().max(100).optional(),
      locality: z.string().max(100).optional(),
      city: z.string().min(2).max(60),
      state: z.string().min(2).max(60),
      pincode: z.string().regex(/^[1-9]\d{5}$/, "PIN code must be 6 digits"),
      latitude: z.number().min(6).max(38),
      longitude: z.number().min(68).max(98),
    }),
  },
  async ({ principal, body }) => prisma.patientAddress.create({ data: { ...body, userId: principal!.userId, verificationStatus: "UNVERIFIED" } }),
);
