import { describe, expect, it } from "vitest";
import { assertProductionSafe, type Env } from "@/lib/env";
import { _redactForTest } from "@/lib/logger";
import { localParts, zonedToUtc } from "@/lib/time";
import { canTransition } from "@/lib/domain/appointment-states";
import { isAvailable, blockWindow } from "@/lib/domain/availability";
import { scoreCandidate } from "@/lib/domain/matching";
import { DEFAULT_MATCHING } from "@/lib/domain/settings";
import { quoteStay } from "@/lib/domain/accommodation";
import { validateUpload } from "@/lib/domain/credentials";
import { CachedRoutingProvider, GoogleRoutesProvider, SimulatedRoutingProvider } from "@/lib/providers/routing";
import { MockPaymentProvider, RazorpayProvider } from "@/lib/providers/payments";
import { createHmac } from "node:crypto";

describe("time", () => {
  it("converts IST wall clock to UTC", () => {
    expect(zonedToUtc("2026-11-02", "10:00").toISOString()).toBe("2026-11-02T04:30:00.000Z");
    expect(zonedToUtc("2026-11-02", "02:00").toISOString()).toBe("2026-11-01T20:30:00.000Z");
    expect(localParts(new Date("2026-11-02T04:30:00Z"))).toMatchObject({ dayOfWeek: 1, minuteOfDay: 600, date: "2026-11-02" });
  });
});

describe("availability", () => {
  const weekly = [{ id: "a", nurseId: "n", dayOfWeek: 1, startMinute: 480, endMinute: 1200, timezone: "Asia/Kolkata" }];
  const start = zonedToUtc("2026-11-02", "10:00");
  const w = blockWindow(start, 60, { travelBufferMinutes: 15, appointmentBufferMinutes: 10 });
  it("accepts a slot within working hours", () => expect(isAvailable(start, w.endAt, w, weekly, [], []).ok).toBe(true));
  it("rejects outside working hours", () => {
    const late = zonedToUtc("2026-11-02", "19:30");
    const lw = blockWindow(late, 60, { travelBufferMinutes: 0, appointmentBufferMinutes: 0 });
    expect(isAvailable(late, lw.endAt, lw, weekly, [], []).reason).toBe("outside_working_hours");
  });
  it("respects travel buffers against existing bookings", () => {
    // Existing booking ends 09:50 + 10-min buffer = 10:00; our block starts 09:45 → overlap.
    const busy = [{ blockStart: zonedToUtc("2026-11-02", "08:45"), blockEnd: zonedToUtc("2026-11-02", "10:00") }];
    expect(isAvailable(start, w.endAt, w, weekly, [], busy).reason).toBe("already_booked");
  });
  it("rejects time off", () => {
    expect(isAvailable(start, w.endAt, w, weekly, [{ startsAt: zonedToUtc("2026-11-02", "09:00"), endsAt: zonedToUtc("2026-11-02", "12:00") }], []).reason).toBe("time_off");
  });
});

describe("appointment state machine", () => {
  it("only nurse can accept", () => {
    expect(canTransition("AWAITING_NURSE_ACCEPTANCE", "CONFIRMED", "NURSE")).toBe(true);
    expect(canTransition("AWAITING_NURSE_ACCEPTANCE", "CONFIRMED", "PATIENT")).toBe(false);
  });
  it("cannot skip to completed", () => expect(canTransition("CONFIRMED", "COMPLETED", "NURSE")).toBe(false));
  it("prescription-gated booking needs admin authorization", () => expect(canTransition("AWAITING_AUTHORIZATION", "AWAITING_NURSE_ACCEPTANCE", "PATIENT")).toBe(false));
});

describe("scoring", () => {
  it("prefers shorter travel all else equal", () => {
    const base = { limit: 120, ratingAvg: 4.5, ratingCount: 10, yearsExperience: 5, languageMatch: 1, completedVisits: 10 };
    expect(scoreCandidate({ ...base, travelMinutes: 20 }, DEFAULT_MATCHING.weights)).toBeGreaterThan(scoreCandidate({ ...base, travelMinutes: 90 }, DEFAULT_MATCHING.weights));
  });
  it("default max travel is 120 minutes", () => expect(DEFAULT_MATCHING.maxTravelMinutes).toBe(120));
});

describe("routing providers", () => {
  it("simulated provider labels its output as simulated and not traffic-aware", async () => {
    const r = await new SimulatedRoutingProvider().estimate({ lat: 12.97, lng: 77.6 }, { lat: 12.93, lng: 77.62 }, new Date());
    expect(r).toMatchObject({ simulated: true, trafficAware: false });
  });
  it("google provider sends departure time and traffic-aware preference, returns null on HTTP error", async () => {
    let sent: Record<string, unknown> = {};
    const depart = new Date(Date.now() + 86_400_000);
    const ok = new GoogleRoutesProvider("k", (async (_u: unknown, init: RequestInit) => {
      sent = JSON.parse(init.body as string);
      return new Response(JSON.stringify({ routes: [{ duration: "3600s", distanceMeters: 25000 }] }));
    }) as typeof fetch);
    expect(await ok.estimate({ lat: 1, lng: 1 }, { lat: 2, lng: 2 }, depart)).toMatchObject({ minutes: 60, distanceKm: 25, trafficAware: true, simulated: false });
    expect(sent).toMatchObject({ routingPreference: "TRAFFIC_AWARE_OPTIMAL", departureTime: depart.toISOString() });
    const bad = new GoogleRoutesProvider("k", (async () => new Response("x", { status: 500 })) as typeof fetch);
    expect(await bad.estimate({ lat: 1, lng: 1 }, { lat: 2, lng: 2 }, depart)).toBeNull();
  });
  it("cache never stores failures and keys on coordinates", async () => {
    const store = new Map<string, unknown>();
    const c = new CachedRoutingProvider(new SimulatedRoutingProvider({ failWith: "null" }), { get: async (k) => (store.get(k) as never) ?? null, set: async (k, v) => void store.set(k, v) }, 60);
    expect(await c.estimate({ lat: 1, lng: 1 }, { lat: 2, lng: 2 }, new Date())).toBeNull();
    expect(store.size).toBe(0);
    const d = new Date();
    expect(CachedRoutingProvider.key("p", { lat: 1, lng: 1 }, { lat: 2, lng: 2 }, d)).not.toBe(CachedRoutingProvider.key("p", { lat: 1.001, lng: 1 }, { lat: 2, lng: 2 }, d));
  });
});

describe("payments", () => {
  it("razorpay signature verification", () => {
    const rp = new RazorpayProvider("id", "secret", "whsec");
    const sig = createHmac("sha256", "secret").update("order_1|pay_1").digest("hex");
    expect(rp.verifyPaymentSignature({ orderId: "order_1", paymentId: "pay_1", signature: sig })).toBe(true);
    expect(rp.verifyPaymentSignature({ orderId: "order_1", paymentId: "pay_2", signature: sig })).toBe(false);
    const body = '{"event":"payment.captured"}';
    expect(rp.verifyWebhook(body, createHmac("sha256", "whsec").update(body).digest("hex"))).toBe(true);
    expect(rp.verifyWebhook(body, "forged")).toBe(false);
    expect(rp.verifyWebhook(body, null)).toBe(false);
  });
  it("mock provider follows the same contract", () => {
    const m = new MockPaymentProvider();
    expect(m.verifyPaymentSignature({ orderId: "o", paymentId: "p", signature: m.sign("o", "p") })).toBe(true);
  });
});

describe("stay pricing", () => {
  const rate = { nightlyInPaise: 200000, monthlyInPaise: 4500000, extendedStayDiscountPct: 10, depositInPaise: 500000 };
  it("nightly for short stays", () => expect(quoteStay(rate, 3).totalInPaise).toBe(600000));
  it("discount for 14+ nights", () => expect(quoteStay(rate, 14).totalInPaise).toBe(2520000));
  it("monthly pricing for 30+ nights", () => expect(quoteStay(rate, 35).totalInPaise).toBe(4500000 + 5 * 200000));
});

describe("security utilities", () => {
  it("rejects disallowed or oversized uploads", () => {
    expect(() => validateUpload("CREDENTIAL", "application/x-msdownload", 100)).toThrow();
    expect(() => validateUpload("CREDENTIAL", "application/pdf", 50 * 1024 * 1024)).toThrow();
    expect(() => validateUpload("CREDENTIAL", "application/pdf", 0)).toThrow();
    expect(() => validateUpload("CREDENTIAL", "application/pdf", 1000)).not.toThrow();
  });
  it("redacts secrets and clinical fields from logs", () => {
    expect(_redactForTest({ otp: "123456", nested: { token: "t", medicalNotes: "x", ok: 1 } })).toEqual({ otp: "[REDACTED]", nested: { token: "[REDACTED]", medicalNotes: "[REDACTED]", ok: 1 } });
  });
  it("production refuses mock providers", () => {
    const e = { NODE_ENV: "production", DATABASE_URL: "x", APP_URL: "https://x", OTP_SECRET: "a-real-secret-value-123", SESSION_TTL_HOURS: 1, SMS_PROVIDER: "mock", ROUTING_PROVIDER: "simulated", PAYMENT_PROVIDER: "mock", STORAGE_PROVIDER: "mock", DEV_EXPOSE_OTP: "false" } as Env;
    expect(() => assertProductionSafe(e)).toThrow(/SMS_PROVIDER=mock/);
    expect(() => assertProductionSafe(e)).toThrow(/ROUTING_PROVIDER=simulated/);
  });
});
