import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { createPrivacyRequest, exportMyData } from "@/lib/domain/privacy";

export const GET = route({ permission: "privacy.self" }, async ({ principal, url }) =>
  url.searchParams.get("export") === "1" ? exportMyData(principal!) : prisma.privacyRequest.findMany({ where: { userId: principal!.userId }, orderBy: { createdAt: "desc" } }),
);

export const POST = route({ permission: "privacy.self", body: z.object({ kind: z.enum(["ACCESS", "CORRECTION", "DELETION", "CONSENT_WITHDRAWAL", "GRIEVANCE"]), details: z.string().max(2000).optional() }) }, async ({ principal, body }) =>
  createPrivacyRequest(principal!, body.kind, body.details),
);
