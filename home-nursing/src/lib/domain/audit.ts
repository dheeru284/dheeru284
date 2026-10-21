import type { Prisma } from "@prisma/client";
import type { Db } from "../db";

export async function audit(db: Db, e: { actorUserId?: string | null; action: string; entityType: string; entityId?: string | null; metadata?: Prisma.InputJsonValue; ip?: string | null }) {
  await db.auditLog.create({ data: { actorUserId: e.actorUserId ?? null, action: e.action, entityType: e.entityType, entityId: e.entityId ?? null, metadata: e.metadata, ip: e.ip ?? null } });
}
