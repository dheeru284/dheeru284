import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { phoneSchema, requestOtp } from "@/lib/auth/otp";
import { rateLimit } from "@/lib/rate-limit";

export const POST = route({ body: z.object({ phone: phoneSchema }) }, async ({ body, req }) => {
  const ip = req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? "unknown";
  await rateLimit(prisma, `otp-ip:${ip}`, 20, 3600);
  return requestOtp(prisma, body.phone);
});
