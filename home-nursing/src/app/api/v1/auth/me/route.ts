import { route } from "@/lib/api";
import { prisma } from "@/lib/db";

export const GET = route({ permission: "authenticated" }, async ({ principal }) => {
  const u = await prisma.user.findUniqueOrThrow({ where: { id: principal!.userId }, select: { id: true, phone: true, fullName: true, email: true, preferredLanguage: true, timezone: true } });
  return { ...u, roles: principal!.roles, permissions: [...principal!.permissions] };
});
