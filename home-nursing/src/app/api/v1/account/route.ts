import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";

/** Self-service profile corrections (name, email, language). Phone changes need re-verification and go through support. */
export const PATCH = route({ permission: "authenticated", body: z.object({ fullName: z.string().min(2).max(100).optional(), email: z.string().email().optional(), preferredLanguage: z.enum(["en", "hi", "kn", "ta", "te", "ml", "mr", "bn"]).optional() }) }, async ({ principal, body }) =>
  prisma.user.update({ where: { id: principal!.userId }, data: body, select: { fullName: true, email: true, preferredLanguage: true } }),
);
