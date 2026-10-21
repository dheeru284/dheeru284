import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { executeDeletion } from "@/lib/domain/privacy";

export const GET = route({ permission: "privacy.manage" }, async () => prisma.privacyRequest.findMany({ where: { status: { in: ["RECEIVED", "IN_PROGRESS"] } }, orderBy: { dueBy: "asc" } }));

export const POST = route({ permission: "privacy.manage", body: z.object({ id: z.string(), action: z.literal("execute_deletion") }) }, async ({ principal, body }) => {
  await executeDeletion(principal!, body.id);
  return { ok: true };
});
