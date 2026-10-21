import { createHash, randomBytes } from "node:crypto";
import type { RoleKey } from "@prisma/client";
import type { Db } from "../db";
import { env } from "../env";
import { AppError } from "../errors";
import { permissionsFor } from "./rbac";

export const SESSION_COOKIE = "hn_session";

export type Principal = { userId: string; roles: RoleKey[]; permissions: Set<string>; sessionId: string };

const tokenHash = (t: string) => createHash("sha256").update(t).digest("hex");

export async function createSession(db: Db, userId: string, userAgent?: string) {
  const token = randomBytes(32).toString("base64url");
  const expiresAt = new Date(Date.now() + env().SESSION_TTL_HOURS * 3600_000);
  await db.session.create({ data: { userId, tokenHash: tokenHash(token), expiresAt, userAgent } });
  return { token, expiresAt };
}

export async function resolveSession(db: Db, token: string | undefined): Promise<Principal | null> {
  if (!token) return null;
  const s = await db.session.findUnique({
    where: { tokenHash: tokenHash(token) },
    include: { user: { include: { roles: { include: { role: true } } } } },
  });
  if (!s || s.revokedAt || s.expiresAt < new Date()) return null;
  if (s.user.status !== "ACTIVE") return null;
  const roles = s.user.roles.map((r) => r.role.key);
  return { userId: s.userId, roles, permissions: permissionsFor(roles), sessionId: s.id };
}

export async function revokeSession(db: Db, sessionId: string) {
  await db.session.update({ where: { id: sessionId }, data: { revokedAt: new Date() } });
}

export function requirePermission(p: Principal | null, perm: string): Principal {
  if (!p) throw new AppError("UNAUTHENTICATED", "Please sign in");
  if (!p.permissions.has(perm)) throw new AppError("FORBIDDEN", "You do not have access to this action");
  return p;
}

export async function grantRole(db: Db, userId: string, key: RoleKey) {
  const role = await db.role.findUniqueOrThrow({ where: { key } });
  await db.userRole.upsert({ where: { userId_roleId: { userId, roleId: role.id } }, create: { userId, roleId: role.id }, update: {} });
}
