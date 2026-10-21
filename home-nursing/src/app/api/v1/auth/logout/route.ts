import { cookies } from "next/headers";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { revokeSession, SESSION_COOKIE } from "@/lib/auth/session";

export const POST = route({ permission: "authenticated" }, async ({ principal }) => {
  await revokeSession(prisma, principal!.sessionId);
  (await cookies()).delete(SESSION_COOKIE);
  return { ok: true };
});
