import { beforeEach, describe, expect, it } from "vitest";
import { cancelStay, extendStay, partnerBookings, partnerRespond, requestStay, searchStays } from "@/lib/domain/accommodation";
import { FakeRouting, makeUser, prisma, resetDb, useFakes } from "./helpers";

let hospitalId: string, propId: string, partner: Awaited<ReturnType<typeof makeUser>>, guest: Awaited<ReturnType<typeof makeUser>>;

async function makeProperty(partnerId: string, name: string, units: number, lat: number, verification = "VERIFIED") {
  return prisma.accommodationProperty.create({
    data: {
      partnerId, name, description: "d", propertyType: "SERVICED_APARTMENT", address: "a", city: "Bengaluru", state: "Karnataka", pincode: "560001", latitude: lat, longitude: 77.64,
      bedrooms: 1, bathrooms: 1, maxGuests: 3, accessibility: ["lift"], minStayNights: 2, cancellationPolicy: "c", verificationStatus: verification,
      units: { create: Array.from({ length: units }, (_, i) => ({ label: `U${i}` })) },
      amenities: { create: [{ amenity: "wifi" }] },
      rates: { create: { nightlyInPaise: 200000, monthlyInPaise: 4500000, extendedStayDiscountPct: 10, depositInPaise: 100000, validFrom: new Date("2000-01-01") } },
    },
  });
}

beforeEach(async () => {
  await resetDb();
  useFakes(new FakeRouting({ "12.9720": 12, "12.9900": 25 }));
  const h = await prisma.hospital.create({ data: { name: "Test Hospital", address: "x", city: "Bengaluru", state: "Karnataka", pincode: "560001", latitude: 12.9719, longitude: 77.6412, dataSource: "test" } });
  hospitalId = h.id;
  partner = await makeUser("+919444444444", ["ACCOMMODATION_PARTNER"]);
  const pr = await prisma.accommodationPartner.create({ data: { userId: partner.userId, businessName: "P" } });
  propId = (await makeProperty(pr.id, "Near", 1, 12.972)).id;
  await makeProperty(pr.id, "Farther", 2, 12.99);
  await makeProperty(pr.id, "Unverified", 1, 12.972, "PENDING");
  guest = await makeUser("+919555555555", ["PATIENT"]);
});

describe("search", () => {
  it("returns verified properties near the hospital, nearest first, with travel estimate", async () => {
    const r = await searchStays(prisma, { hospitalId, checkIn: "2026-12-01", checkOut: "2026-12-05", guests: 2 });
    expect(r.results.map((x) => x.name)).toEqual(["Near", "Farther"]);
    expect(r.results[0]!.travelToHospital).toMatchObject({ minutes: 12 });
    expect(r.results[0]!.quote.totalInPaise).toBe(800000);
  });
  it("hides fully booked properties and enforces minimum stay", async () => {
    await requestStay(guest, { propertyId: propId, checkIn: "2026-12-01", checkOut: "2026-12-05", guests: 1 }, prisma);
    const r = await searchStays(prisma, { hospitalId, checkIn: "2026-12-03", checkOut: "2026-12-06", guests: 1 });
    expect(r.results.map((x) => x.name)).toEqual(["Farther"]);
    await expect(requestStay(guest, { propertyId: propId, checkIn: "2026-12-10", checkOut: "2026-12-11", guests: 1 }, prisma)).rejects.toMatchObject({ code: "VALIDATION" });
  });
  it("blackouts remove a property", async () => {
    await prisma.propertyAvailability.create({ data: { propertyId: propId, startDate: new Date("2026-12-02"), endDate: new Date("2026-12-03") } });
    const r = await searchStays(prisma, { hospitalId, checkIn: "2026-12-01", checkOut: "2026-12-05", guests: 1 });
    expect(r.results.map((x) => x.name)).toEqual(["Farther"]);
  });
});

describe("booking integrity", () => {
  it("rejects overlapping stays on a single-unit property; adjacent stays are fine", async () => {
    await requestStay(guest, { propertyId: propId, checkIn: "2026-12-01", checkOut: "2026-12-05", guests: 1 }, prisma);
    await expect(requestStay(guest, { propertyId: propId, checkIn: "2026-12-04", checkOut: "2026-12-08", guests: 1 }, prisma)).rejects.toMatchObject({ code: "CONFLICT" });
    await expect(requestStay(guest, { propertyId: propId, checkIn: "2026-12-05", checkOut: "2026-12-08", guests: 1 }, prisma)).resolves.toBeTruthy();
  });
  it("concurrent requests for the last unit: exactly one wins", async () => {
    const rs = await Promise.allSettled([1, 2, 3, 4].map(() => requestStay(guest, { propertyId: propId, checkIn: "2027-01-01", checkOut: "2027-02-15", guests: 1 }, prisma)));
    expect(rs.filter((r) => r.status === "fulfilled")).toHaveLength(1);
  });
  it("long stays use monthly pricing", async () => {
    const b = await requestStay(guest, { propertyId: propId, checkIn: "2027-01-01", checkOut: "2027-02-15", guests: 1 }, prisma);
    expect(b.totalInPaise).toBe(4500000 + 15 * 200000);
  });
  it("extension succeeds when free and fails on conflict; cancellation frees dates", async () => {
    const b = await requestStay(guest, { propertyId: propId, checkIn: "2026-12-01", checkOut: "2026-12-05", guests: 1 }, prisma);
    await partnerRespond(partner, b.id, "CONFIRMED", prisma);
    const ext = await extendStay(guest, b.id, "2026-12-08", prisma);
    expect(ext.checkIn.toISOString().slice(0, 10)).toBe("2026-12-05");
    const other = await makeUser("+919666666666", ["PATIENT"]);
    const blocker = await requestStay(other, { propertyId: propId, checkIn: "2026-12-08", checkOut: "2026-12-12", guests: 1 }, prisma);
    await partnerRespond(partner, ext.id, "CONFIRMED", prisma);
    await expect(extendStay(guest, ext.id, "2026-12-10", prisma)).rejects.toMatchObject({ code: "CONFLICT" });
    await cancelStay(other, blocker.id, prisma);
    await expect(extendStay(guest, ext.id, "2026-12-10", prisma)).resolves.toBeTruthy();
  });
});

describe("partner isolation", () => {
  it("partners see only their bookings and cannot act on others'", async () => {
    const b = await requestStay(guest, { propertyId: propId, checkIn: "2026-12-01", checkOut: "2026-12-05", guests: 1 }, prisma);
    const rival = await makeUser("+919777777777", ["ACCOMMODATION_PARTNER"]);
    await prisma.accommodationPartner.create({ data: { userId: rival.userId, businessName: "R" } });
    expect(await partnerBookings(rival, prisma)).toHaveLength(0);
    await expect(partnerRespond(rival, b.id, "CONFIRMED", prisma)).rejects.toMatchObject({ code: "NOT_FOUND" });
    const mine = await partnerBookings(partner, prisma);
    expect(mine).toHaveLength(1);
    expect(Object.keys(mine[0]!.guest)).toEqual(["name", "phone"]); // no clinical or appointment data
  });
  it("guests cannot cancel others' stays", async () => {
    const b = await requestStay(guest, { propertyId: propId, checkIn: "2026-12-01", checkOut: "2026-12-05", guests: 1 }, prisma);
    const other = await makeUser("+919888888888", ["PATIENT"]);
    await expect(cancelStay(other, b.id, prisma)).rejects.toMatchObject({ code: "NOT_FOUND" });
  });
});
