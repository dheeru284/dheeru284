import { cookies } from "next/headers";
import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { env } from "@/lib/env";
import { phoneSchema, verifyOtp } from "@/lib/auth/otp";
import { createSession, grantRole, SESSION_COOKIE } from "@/lib/auth/session";
import { audit } from "@/lib/domain/audit";

// Self-registration may only request these roles. Admin/compliance/support roles are granted by admins.
const SELF_ROLES = ["PATIENT", "NURSE", "ACCOMMODATION_PARTNER"] as const;

export const POST = route(
  { body: z.object({ challengeId: z.string(), phone: phoneSchema, code: z.string().regex(/^\d{6}$/), registerAs: z.enum(SELF_ROLES).default("PATIENT"), fullName: z.string().min(2).max(100).optional() }) },
  async ({ body, req }) => {
    await verifyOtp(prisma, body.challengeId, body.phone, body.code);
    let user = await prisma.user.findUnique({ where: { phone: body.phone } });
    const isNew = !user;
    if (!user) user = await prisma.user.create({ data: { phone: body.phone, fullName: body.fullName } });
    const roles = await prisma.userRole.count({ where: { userId: user.id } });
    if (isNew || roles === 0) await grantRole(prisma, user.id, body.registerAs);
    const { token, expiresAt } = await createSession(prisma, user.id, req.headers.get("user-agent") ?? undefined);
    (await cookies()).set(SESSION_COOKIE, token, { httpOnly: true, secure: env().NODE_ENV === "production", sameSite: "lax", path: "/", expires: expiresAt });
    await audit(prisma, { actorUserId: user.id, action: isNew ? "auth.register" : "auth.login", entityType: "User", entityId: user.id });
    return { userId: user.id, isNew };
  },
);
