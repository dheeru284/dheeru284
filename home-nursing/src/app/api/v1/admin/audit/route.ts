import { pageParams, route } from "@/lib/api";
import { prisma } from "@/lib/db";

export const GET = route({ permission: "audit.read" }, async ({ url }) => {
  const entityType = url.searchParams.get("entityType") ?? undefined;
  return prisma.auditLog.findMany({ where: entityType ? { entityType } : {}, orderBy: { createdAt: "desc" }, ...pageParams(url) });
});
