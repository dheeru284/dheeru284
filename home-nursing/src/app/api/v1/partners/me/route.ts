import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";

export const GET = route({ permission: "partner.self" }, async ({ principal }) =>
  prisma.accommodationPartner.findUnique({ where: { userId: principal!.userId }, include: { properties: { include: { units: true, rates: true, amenities: true } } } }),
);

export const PUT = route({ permission: "partner.self", body: z.object({ businessName: z.string().min(2).max(120), gstin: z.string().regex(/^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/).optional() }) }, async ({ principal, body }) =>
  prisma.accommodationPartner.upsert({ where: { userId: principal!.userId }, create: { ...body, userId: principal!.userId }, update: body }),
);
