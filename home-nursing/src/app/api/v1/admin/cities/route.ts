import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { audit } from "@/lib/domain/audit";

export const GET = route({ permission: "admin.access" }, async () => prisma.city.findMany({ orderBy: [{ state: "asc" }, { name: "asc" }] }));

export const POST = route({ permission: "locations.manage", body: z.object({ name: z.string().min(2), state: z.string().min(2), isActive: z.boolean().default(true) }) }, async ({ principal, body }) => {
  const c = await prisma.city.upsert({ where: { name_state: { name: body.name, state: body.state } }, create: body, update: { isActive: body.isActive } });
  await audit(prisma, { actorUserId: principal!.userId, action: "city.upsert", entityType: "City", entityId: c.id, metadata: body });
  return c;
});
