import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { AppError } from "@/lib/errors";
import { providers } from "@/lib/providers";
import { audit } from "@/lib/domain/audit";
import { decideDocument, decideRegistration } from "@/lib/domain/credentials";

/** GET: short-lived signed download URL for a credential document (access is audited). */
export const GET = route({ permission: "nurse.verify" }, async ({ principal, params }) => {
  if (params.kind !== "documents") throw new AppError("NOT_FOUND", "Not found");
  const d = await prisma.credentialDocument.findUnique({ where: { id: params.id! } });
  if (!d) throw new AppError("NOT_FOUND", "Document not found");
  await audit(prisma, { actorUserId: principal!.userId, action: "credential.document.view", entityType: "CredentialDocument", entityId: d.id });
  return providers().storage.presignDownload(d.storageKey);
});

export const POST = route(
  { permission: "nurse.verify", body: z.object({ decision: z.enum(["VERIFIED", "REJECTED", "REVOKED"]), method: z.string().min(3).max(80), notes: z.string().max(1000).optional() }) },
  async ({ principal, params, body }) => {
    if (params.kind === "documents") await decideDocument(principal!, params.id!, body.decision, body.method, body.notes);
    else if (params.kind === "registrations") await decideRegistration(principal!, params.id!, body.decision, body.method, body.notes);
    else throw new AppError("NOT_FOUND", "Not found");
    return { ok: true };
  },
);
