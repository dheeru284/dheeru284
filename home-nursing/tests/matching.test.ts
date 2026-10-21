import { beforeEach, describe, expect, it } from "vitest";
import { findMatches } from "@/lib/domain/matching";
import { updateSetting } from "@/lib/domain/settings";
import { at, FakeRouting, makeNurse, makePatient, makeService, makeUser, NOW, prisma, resetDb, useFakes } from "./helpers";

// Nurse origin latitudes double as keys into the fake routing table.
const NEAR = 12.9701, FAR = 12.9702, EDGE = 12.9703, DOWN = 12.9704;
let routing: FakeRouting;
let svc: Awaited<ReturnType<typeof makeService>>;
const loc = { lat: 12.95, lng: 77.6, city: "Bengaluru", state: "Karnataka" };

beforeEach(async () => {
  await resetDb();
  routing = new FakeRouting({ [NEAR.toFixed(4)]: 30, [FAR.toFixed(4)]: 150, [EDGE.toFixed(4)]: 120, [DOWN.toFixed(4)]: "throw" });
  useFakes(routing);
  svc = await makeService();
});

const match = (over: Partial<Parameters<typeof findMatches>[1]> = {}) => findMatches(prisma, { serviceId: svc.id, location: loc, startAt: at(), ...over }, NOW);

describe("travel-time threshold", () => {
  it("includes nurses within 120 minutes (inclusive) and excludes those beyond", async () => {
    const near = await makeNurse(svc.id, { lat: NEAR });
    const edge = await makeNurse(svc.id, { lat: EDGE });
    await makeNurse(svc.id, { lat: FAR });
    const r = await match();
    expect(r.appliedLimitMinutes).toBe(120);
    expect(r.results.map((x) => x.nurseId).sort()).toEqual([near.nurse.id, edge.nurse.id].sort());
    expect(r.excludedCounts.beyond_travel_limit).toBe(1);
    expect(r.results[0]!.nurseId).toBe(near.nurse.id); // closer ranks first
    expect(r.results[0]!.travel).toMatchObject({ minutes: 30, source: "fake", unavailable: false });
  });

  it("admin can change the threshold at runtime without code changes", async () => {
    await makeNurse(svc.id, { lat: FAR });
    expect((await match()).results).toHaveLength(0);
    const admin = await makeUser("+919000000001", ["ADMIN"]);
    await updateSetting(prisma, "matching", { maxTravelMinutes: 180 }, admin.userId);
    const r = await match();
    expect(r.appliedLimitMinutes).toBe(180);
    expect(r.results).toHaveLength(1);
    expect(await prisma.auditLog.count({ where: { action: "settings.update" } })).toBe(1);
  });

  it("rejects invalid threshold values", async () => {
    const admin = await makeUser("+919000000001", ["ADMIN"]);
    await expect(updateSetting(prisma, "matching", { maxTravelMinutes: -5 }, admin.userId)).rejects.toMatchObject({ code: "VALIDATION" });
  });

  it("nurse's own travel limit is respected", async () => {
    await makeNurse(svc.id, { lat: NEAR, maxTravelMinutes: 20 });
    expect((await match()).results).toHaveLength(0);
  });

  it("never silently expands the limit; expansion requires admin permission", async () => {
    await makeNurse(svc.id, { lat: FAR });
    const r = await match();
    expect(r.results).toHaveLength(0);
    expect(r.limitExpanded).toBe(false);
    expect(r.emptyReason).toMatch(/120-minute/);
    expect(r.suggestions!.length).toBeGreaterThan(0);
    await expect(match({ requestExpandedLimit: true })).rejects.toMatchObject({ code: "FORBIDDEN" });
    const admin = await makeUser("+919000000001", ["ADMIN"]);
    await updateSetting(prisma, "matching", { allowPatientExpansion: true, expansionMaxMinutes: 160 }, admin.userId);
    const x = await match({ requestExpandedLimit: true });
    expect(x.limitExpanded).toBe(true);
    expect(x.results).toHaveLength(1);
  });

  it("uses the appointment date/time for the routing departure", async () => {
    await makeNurse(svc.id, { lat: NEAR });
    const r = await match();
    const depart = routing.calls[0]!.departAt;
    expect(depart.toISOString()).toBe(r.departureTimeUsed);
    expect(depart.getTime()).toBeLessThan(at().getTime());
    expect(at().getTime() - depart.getTime()).toBeLessThanOrEqual(3 * 3600_000);
  });
});

describe("routing failure", () => {
  it("excludes nurses when the estimate is unavailable (default policy) — never invents a time", async () => {
    await makeNurse(svc.id, { lat: DOWN });
    await makeNurse(svc.id, { lat: 12.9799 }); // provider returns null
    const r = await match();
    expect(r.results).toHaveLength(0);
    expect(r.excludedCounts.travel_estimate_unavailable).toBe(2);
  });
  it("flagged-inclusion policy labels results as unavailable with no minutes", async () => {
    const admin = await makeUser("+919000000001", ["ADMIN"]);
    await updateSetting(prisma, "matching", { routingUnavailablePolicy: "INCLUDE_FLAGGED_MANUAL_CONFIRM" }, admin.userId);
    await makeNurse(svc.id, { lat: DOWN });
    const r = await match();
    expect(r.results[0]!.travel).toMatchObject({ minutes: null, unavailable: true, source: "UNAVAILABLE" });
  });
});

describe("eligibility", () => {
  it("pending, rejected, unverified and expired nurses are not bookable", async () => {
    await makeNurse(svc.id, { lat: NEAR, status: "PENDING_VERIFICATION", credential: "PENDING" });
    await makeNurse(svc.id, { lat: NEAR, credential: "PENDING" }); // approved flag but docs not verified
    await makeNurse(svc.id, { lat: NEAR, credential: "REJECTED" });
    await makeNurse(svc.id, { lat: NEAR, docExpires: new Date("2026-10-30") });
    const ok = await makeNurse(svc.id, { lat: NEAR });
    const r = await match();
    expect(r.results.map((x) => x.nurseId)).toEqual([ok.nurse.id]);
    expect(r.excludedCounts.credentials).toBe(3);
  });
  it("only nurses approved for the requested service are returned", async () => {
    const other = await makeService({ slug: "wound" });
    await makeNurse(other.id, { lat: NEAR });
    expect((await match()).results).toHaveLength(0);
  });
  it("invasive services are not bookable until clinically approved", async () => {
    const inj = await makeService({ slug: "inj", isInvasive: true });
    await makeNurse(inj.id, { lat: NEAR });
    await expect(findMatches(prisma, { serviceId: inj.id, location: loc, startAt: at() }, NOW)).rejects.toMatchObject({ code: "PRECONDITION_FAILED" });
  });
  it("applies gender preference", async () => {
    await makeNurse(svc.id, { lat: NEAR, gender: "MALE" });
    const f = await makeNurse(svc.id, { lat: NEAR, gender: "FEMALE" });
    const r = await match({ genderPreference: "FEMALE" });
    expect(r.results.map((x) => x.nurseId)).toEqual([f.nurse.id]);
  });
  it("excludes unavailable nurses (day off) and overlapping bookings", async () => {
    await makeNurse(svc.id, { lat: NEAR, days: [0] }); // Sundays only; request is Monday
    const busy = await makeNurse(svc.id, { lat: NEAR });
    const { patient, address } = await makePatient();
    await prisma.appointment.create({ data: { reference: "X1", patientId: patient.id, bookedByUserId: patient.accountUserId, nurseId: busy.nurse.id, serviceId: svc.id, addressId: address.id, startAt: at("10:30"), endAt: at("11:30"), blockStart: at("10:15"), blockEnd: at("11:40"), status: "CONFIRMED", amountInPaise: 1, commissionInPaise: 0 } });
    const r = await match();
    expect(r.results).toHaveLength(0);
    expect(r.excludedCounts.outside_working_hours).toBe(1);
    expect(r.excludedCounts.already_booked).toBe(1);
  });
  it("results never expose nurse coordinates", async () => {
    await makeNurse(svc.id, { lat: NEAR });
    const r = await match();
    expect(JSON.stringify(r)).not.toContain(String(NEAR));
  });
  it("enforces booking cutoff", async () => {
    await expect(findMatches(prisma, { serviceId: svc.id, location: loc, startAt: new Date(NOW.getTime() + 30 * 60_000) }, NOW)).rejects.toMatchObject({ code: "VALIDATION" });
  });
});
