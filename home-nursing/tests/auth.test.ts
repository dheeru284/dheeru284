import { beforeEach, describe, expect, it } from "vitest";
import { requestOtp, verifyOtp } from "@/lib/auth/otp";
import { createSession, requirePermission, resolveSession, revokeSession } from "@/lib/auth/session";
import { AppError } from "@/lib/errors";
import { FakeRouting, makeUser, prisma, resetDb, useFakes } from "./helpers";

const phone = "+919876543210";
let sms: ReturnType<typeof useFakes>["sms"];
const lastCode = () => sms.outbox.at(-1)!.body.slice(0, 6);

beforeEach(async () => {
  await resetDb();
  ({ sms } = useFakes(new FakeRouting({})));
});

describe("OTP", () => {
  it("valid code verifies once only", async () => {
    const { challengeId, devCode } = await requestOtp(prisma, phone);
    expect(devCode).toBeUndefined(); // never exposed unless DEV_EXPOSE_OTP=true
    await verifyOtp(prisma, challengeId, phone, lastCode());
    await expect(verifyOtp(prisma, challengeId, phone, lastCode())).rejects.toThrow(/Invalid or expired/);
  });
  it("wrong code fails and counts attempts; locks after max", async () => {
    const { challengeId } = await requestOtp(prisma, phone);
    const wrong = lastCode() === "000000" ? "111111" : "000000";
    for (let i = 0; i < 5; i++) await expect(verifyOtp(prisma, challengeId, phone, wrong)).rejects.toThrow();
    await expect(verifyOtp(prisma, challengeId, phone, lastCode())).rejects.toMatchObject({ code: "RATE_LIMITED" });
  });
  it("expired code fails", async () => {
    const { challengeId } = await requestOtp(prisma, phone);
    await prisma.otpChallenge.update({ where: { id: challengeId }, data: { expiresAt: new Date(Date.now() - 1000) } });
    await expect(verifyOtp(prisma, challengeId, phone, lastCode())).rejects.toThrow();
  });
  it("code is bound to the phone number", async () => {
    const { challengeId } = await requestOtp(prisma, phone);
    await expect(verifyOtp(prisma, challengeId, "+919876543211", lastCode())).rejects.toThrow();
  });
  it("rate-limits OTP requests per phone", async () => {
    for (let i = 0; i < 5; i++) await requestOtp(prisma, phone);
    await expect(requestOtp(prisma, phone)).rejects.toMatchObject({ code: "RATE_LIMITED" });
  });
  it("stores only a hash of the code", async () => {
    const { challengeId } = await requestOtp(prisma, phone);
    const row = await prisma.otpChallenge.findUniqueOrThrow({ where: { id: challengeId } });
    expect(row.codeHash).not.toContain(lastCode());
  });
  it("rejects non-Indian mobile numbers", async () => {
    await expect(requestOtp(prisma, "+15551234567")).rejects.toThrow();
  });
});

describe("sessions & RBAC", () => {
  it("expired and revoked sessions do not resolve", async () => {
    const u = await makeUser("+919000000099", ["PATIENT"]);
    const s = await createSession(prisma, u.userId);
    const p = await resolveSession(prisma, s.token);
    expect(p?.roles).toEqual(["PATIENT"]);
    await revokeSession(prisma, p!.sessionId);
    expect(await resolveSession(prisma, s.token)).toBeNull();
    const s2 = await createSession(prisma, u.userId);
    await prisma.session.updateMany({ where: { revokedAt: null }, data: { expiresAt: new Date(Date.now() - 1) } });
    expect(await resolveSession(prisma, s2.token)).toBeNull();
    expect(await resolveSession(prisma, "garbage")).toBeNull();
  });
  it("suspended users lose access", async () => {
    const u = await makeUser("+919000000098", ["PATIENT"]);
    const s = await createSession(prisma, u.userId);
    await prisma.user.update({ where: { id: u.userId }, data: { status: "SUSPENDED" } });
    expect(await resolveSession(prisma, s.token)).toBeNull();
  });
  it("patients cannot perform nurse or admin actions; admins lack raw clinical access", async () => {
    const pt = await makeUser("+919000000097", ["PATIENT"]);
    const admin = await makeUser("+919000000096", ["ADMIN"]);
    expect(() => requirePermission(pt, "nurse.verify")).toThrow(AppError);
    expect(() => requirePermission(pt, "visit.record")).toThrow(AppError);
    expect(() => requirePermission(null, "patient.self")).toThrow(/sign in/);
    expect(admin.permissions.has("nurse.verify")).toBe(true);
    expect(admin.permissions.has("clinical.read")).toBe(false);
  });
});
