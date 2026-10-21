import { pageParams, route } from "@/lib/api";
import { prisma } from "@/lib/db";

export const GET = route({ permission: "authenticated" }, async ({ principal, url }) =>
  prisma.notification.findMany({ where: { userId: principal!.userId, channel: "IN_APP" }, orderBy: { createdAt: "desc" }, ...pageParams(url) }),
);
