import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { AppError } from "@/lib/errors";
import { audit } from "@/lib/domain/audit";

// Flags that cannot be switched on from the UI because the feature does not exist yet / needs regulatory review.
const LOCKED = new Set(["medicine_delivery"]);

export const GET = route({ permission: "admin.access" }, async () => prisma.featureFlag.findMany({ orderBy: { key: "asc" } }));

export const PUT = route({ permission: "flags.write", body: z.object({ key: z.string(), enabled: z.boolean(), rolloutCities: z.array(z.string()).optional() }) }, async ({ principal, body }) => {
  if (LOCKED.has(body.key) && body.enabled) throw new AppError("FEATURE_DISABLED", "This feature is locked pending regulatory review and is not implemented in this release");
  const f = await prisma.featureFlag.update({ where: { key: body.key }, data: { enabled: body.enabled, ...(body.rolloutCities ? { rolloutCities: body.rolloutCities } : {}) } });
  await audit(prisma, { actorUserId: principal!.userId, action: "flag.update", entityType: "FeatureFlag", entityId: body.key, metadata: { enabled: body.enabled } });
  return f;
});
