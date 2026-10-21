import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { audit } from "@/lib/domain/audit";

export const GET = route({ permission: "partners.manage" }, async () => prisma.accommodationPartner.findMany({ include: { user: { select: { phone: true } }, _count: { select: { properties: true } } }, orderBy: { createdAt: "desc" } }));

export const POST = route({ permission: "partners.manage", body: z.object({ id: z.string(), verificationStatus: z.enum(["VERIFIED", "REJECTED", "PENDING"]) }) }, async ({ principal, body }) => {
  const p = await prisma.accommodationPartner.update({ where: { id: body.id }, data: { verificationStatus: body.verificationStatus } });
  await audit(prisma, { actorUserId: principal!.userId, action: "partner.verify", entityType: "AccommodationPartner", entityId: p.id, metadata: body });
  return p;
});
