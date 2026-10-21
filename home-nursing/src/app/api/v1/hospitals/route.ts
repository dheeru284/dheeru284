import { z } from "zod";
import { pageParams, route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { audit } from "@/lib/domain/audit";

export const GET = route({}, async ({ url }) => {
  const q = url.searchParams.get("q")?.trim();
  const city = url.searchParams.get("city")?.trim();
  return prisma.hospital.findMany({
    where: { isActive: true, mergedIntoId: null, ...(city ? { city: { equals: city, mode: "insensitive" } } : {}), ...(q ? { OR: [{ name: { contains: q, mode: "insensitive" } }, { address: { contains: q, mode: "insensitive" } }] } : {}) },
    select: { id: true, name: true, address: true, city: true, state: true, pincode: true, latitude: true, longitude: true, specialties: true, verificationStatus: true, website: true },
    orderBy: { name: "asc" },
    ...pageParams(url),
  });
});

export const POST = route(
  { permission: "hospital.manage", body: z.object({ name: z.string().min(2), address: z.string(), city: z.string(), state: z.string(), pincode: z.string().regex(/^[1-9]\d{5}$/), latitude: z.number(), longitude: z.number(), phone: z.string().optional(), website: z.string().url().optional(), specialties: z.array(z.string()).default([]), dataSource: z.string().min(2) }) },
  async ({ principal, body }) => {
    const h = await prisma.hospital.create({ data: body });
    await audit(prisma, { actorUserId: principal!.userId, action: "hospital.create", entityType: "Hospital", entityId: h.id });
    return h;
  },
);
