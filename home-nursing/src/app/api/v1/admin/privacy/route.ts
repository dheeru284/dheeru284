import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { audit } from "@/lib/domain/audit";
import { executeDeletion } from "@/lib/domain/privacy";

export const GET = route({ permission: "privacy.manage" }, async () => prisma.privacyRequest.findMany({ where: { status: { in: ["RECEIVED", "IN_PROGRESS"] } }, orderBy: { dueBy: "asc" } }));

export const POST = route(
  { permission: "privacy.manage", body: z.union([z.object({ id: z.string(), action: z.literal("execute_deletion") }), z.object({ id: z.string(), action: z.literal("set_status"), status: z.enum(["IN_PROGRESS", "COMPLETED", "REJECTED"]), note: z.string().max(1000).optional() })]) },
  async ({ principal, body }) => {
    if (body.action === "execute_deletion") await executeDeletion(principal!, body.id);
    else {
      await prisma.privacyRequest.update({ where: { id: body.id }, data: { status: body.status, ...(body.status !== "IN_PROGRESS" ? { resolvedAt: new Date() } : {}) } });
      await audit(prisma, { actorUserId: principal!.userId, action: `privacy.request.${body.status.toLowerCase()}`, entityType: "PrivacyRequest", entityId: body.id, metadata: { note: body.note ?? null } });
    }
    return { ok: true };
  },
);
