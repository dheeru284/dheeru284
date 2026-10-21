import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { audit } from "@/lib/domain/audit";

export const GET = route({ permission: "property.verify" }, async ({ url }) =>
  prisma.accommodationProperty.findMany({ where: { verificationStatus: url.searchParams.get("status") ?? "PENDING" }, include: { partner: { select: { businessName: true } } } }),
);

export const POST = route({ permission: "property.verify", body: z.object({ id: z.string(), decision: z.enum(["VERIFIED", "REJECTED"]), notes: z.string().max(500).optional() }) }, async ({ principal, body }) => {
  const p = await prisma.accommodationProperty.update({ where: { id: body.id }, data: { verificationStatus: body.decision } });
  await audit(prisma, { actorUserId: principal!.userId, action: "property.verify", entityType: "AccommodationProperty", entityId: p.id, metadata: { decision: body.decision, notes: body.notes ?? null } });
  return p;
});
