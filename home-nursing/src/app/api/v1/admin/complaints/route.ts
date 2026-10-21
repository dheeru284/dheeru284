import { z } from "zod";
import { pageParams, route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { audit } from "@/lib/domain/audit";

export const GET = route({ permission: "complaint.manage" }, async ({ url }) => {
  const [complaints, incidents] = await Promise.all([
    prisma.complaint.findMany({ where: { status: { in: ["OPEN", "INVESTIGATING"] } }, orderBy: [{ severity: "desc" }, { createdAt: "asc" }], ...pageParams(url) }),
    prisma.incident.findMany({ where: { status: "OPEN" }, orderBy: { createdAt: "asc" } }),
  ]);
  return { complaints, incidents };
});

export const PATCH = route({ permission: "complaint.manage", body: z.object({ id: z.string(), status: z.enum(["INVESTIGATING", "RESOLVED", "DISMISSED"]), resolution: z.string().max(2000).optional() }) }, async ({ principal, body }) => {
  const c = await prisma.complaint.update({ where: { id: body.id }, data: { status: body.status, resolution: body.resolution, assignedToUserId: principal!.userId } });
  await audit(prisma, { actorUserId: principal!.userId, action: "complaint.update", entityType: "Complaint", entityId: c.id, metadata: { status: body.status } });
  return c;
});
