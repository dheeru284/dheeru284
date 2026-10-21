import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { AppError } from "@/lib/errors";
import { providers } from "@/lib/providers";
import { audit } from "@/lib/domain/audit";
import { decideAuthorization } from "@/lib/domain/appointments";

/** Short-lived signed link to view a prescription; every view is audited. */
export const GET = route({ permission: "authorization.review" }, async ({ principal, params }) => {
  const d = await prisma.appointmentDocument.findUnique({ where: { id: params.docId! } });
  if (!d) throw new AppError("NOT_FOUND", "Document not found");
  await audit(prisma, { actorUserId: principal!.userId, action: "authorization.document.view", entityType: "AppointmentDocument", entityId: d.id });
  return providers().storage.presignDownload(d.storageKey);
});

export const POST = route({ permission: "authorization.review", body: z.object({ decision: z.enum(["VERIFIED", "REJECTED"]), notes: z.string().max(1000).optional() }) }, async ({ principal, params, body }) => {
  await decideAuthorization(principal!, params.docId!, body.decision, body.notes);
  return { ok: true };
});
