import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { audit } from "@/lib/domain/audit";

export const POST = route({ permission: "nurse.verify", body: z.object({ decision: z.enum(["VERIFIED", "REJECTED"]) }) }, async ({ principal, params, body }) => {
  const q = await prisma.nurseQualification.update({ where: { id: params.id! }, data: { verificationStatus: body.decision } });
  await audit(prisma, { actorUserId: principal!.userId, action: "qualification.decide", entityType: "NurseQualification", entityId: q.id, metadata: { decision: body.decision } });
  return q;
});
