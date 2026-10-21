import { createHmac, randomInt, timingSafeEqual } from "node:crypto";
import { z } from "zod";
import type { Db } from "../db";
import { env } from "../env";
import { AppError } from "../errors";
import { providers } from "../providers";
import { rateLimit } from "../rate-limit";

export const OTP_TTL_MS = 5 * 60_000;
export const OTP_MAX_ATTEMPTS = 5;

export const phoneSchema = z.string().regex(/^\+91[6-9]\d{9}$/, "Enter a valid Indian mobile number (+91XXXXXXXXXX)");

const hash = (phone: string, code: string) => createHmac("sha256", env().OTP_SECRET).update(`${phone}|${code}`).digest("hex");

export async function requestOtp(db: Db, phone: string): Promise<{ challengeId: string; devCode?: string }> {
  phoneSchema.parse(phone);
  await rateLimit(db, `otp:${phone}`, 5, 15 * 60);
  const code = String(randomInt(0, 1_000_000)).padStart(6, "0");
  const ch = await db.otpChallenge.create({ data: { phone, codeHash: hash(phone, code), expiresAt: new Date(Date.now() + OTP_TTL_MS) } });
  // Message deliberately contains no health information.
  await providers().sms.send(phone, `${code} is your verification code. It expires in 5 minutes. Do not share it with anyone.`);
  const expose = env().NODE_ENV !== "production" && env().DEV_EXPOSE_OTP === "true";
  return { challengeId: ch.id, ...(expose ? { devCode: code } : {}) };
}

export async function verifyOtp(db: Db, challengeId: string, phone: string, code: string): Promise<void> {
  const ch = await db.otpChallenge.findUnique({ where: { id: challengeId } });
  if (!ch || ch.phone !== phone) throw new AppError("UNAUTHENTICATED", "Invalid or expired code");
  if (ch.consumedAt || ch.expiresAt < new Date()) throw new AppError("UNAUTHENTICATED", "Invalid or expired code");
  if (ch.attempts >= OTP_MAX_ATTEMPTS) throw new AppError("RATE_LIMITED", "Too many attempts. Request a new code.");
  const ok = timingSafeEqual(Buffer.from(hash(phone, code)), Buffer.from(ch.codeHash));
  if (!ok) {
    await db.otpChallenge.update({ where: { id: ch.id }, data: { attempts: { increment: 1 } } });
    throw new AppError("UNAUTHENTICATED", "Invalid or expired code");
  }
  // Conditional update makes consumption single-use even under concurrent verification.
  const consumed = await db.otpChallenge.updateMany({ where: { id: ch.id, consumedAt: null }, data: { consumedAt: new Date() } });
  if (consumed.count !== 1) throw new AppError("UNAUTHENTICATED", "Invalid or expired code");
}
