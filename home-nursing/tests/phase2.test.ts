import { beforeEach, describe, expect, it } from "vitest";
import { createAppointment, decideAuthorization, receiptFor, rescheduleAppointment, startPrescriptionUpload, transitionAppointment } from "@/lib/domain/appointments";
import { addBlackout, partnerRespond, partnerStayTransition, requestStay, searchStays, setRate } from "@/lib/domain/accommodation";
import { confirmPayment, createStayOrder, generateSettlements, reconciliationReport } from "@/lib/domain/payments";
import { applyRetention, mergeHospitals, moderateReview, suspiciousActivity, toCsv, updateHospital } from "@/lib/domain/admin";
import { dispatchPending, notify } from "@/lib/domain/notifications";
import { S3StorageProvider } from "@/lib/providers/storage";
import { Msg91SmsProvider } from "@/lib/providers/sms";
import { GoogleGeocodingProvider } from "@/lib/providers/geocoding";
import { MockEmailProvider } from "@/lib/providers/channels";
import { setProviders } from "@/lib/providers";
import { at, FakeRouting, makeNurse, makePatient, makeService, makeUser, NOW, prisma, resetDb, useFakes } from "./helpers";

let payments: ReturnType<typeof useFakes>["payments"];
let svc: Awaited<ReturnType<typeof makeService>>;
let nurse: Awaited<ReturnType<typeof makeNurse>>;
let pt: Awaited<ReturnType<typeof makePatient>>;
const base = () => ({ patientId: pt.patient.id, nurseId: nurse.nurse.id, serviceId: svc.id, addressId: pt.address.id });

beforeEach(async () => {
  await resetDb();
  ({ payments } = useFakes(new FakeRouting({ "12.9701": 30, "12.9720": 10 })));
  svc = await makeService();
  nurse = await makeNurse(svc.id, { lat: 12.9701 });
  pt = await makePatient();
});

describe("atomic reschedule", () => {
  it("can move into a slot overlapping its own old slot; links the new booking", async () => {
    const a = await createAppointment(pt.principal, { ...base(), startAt: at("10:00") }, prisma, NOW);
    const b = await rescheduleAppointment(pt.principal, a.id, at("10:30"), prisma, NOW);
    expect(b.rescheduledFromId).toBe(a.id);
    expect((await prisma.appointment.findUniqueOrThrow({ where: { id: a.id } })).status).toBe("RESCHEDULED");
  });
  it("a failing reschedule leaves the original untouched (single transaction)", async () => {
    const a = await createAppointment(pt.principal, { ...base(), startAt: at("10:00") }, prisma, NOW);
    const other = await makePatient("+919444000001");
    await createAppointment(other.principal, { ...base(), patientId: other.patient.id, addressId: other.address.id, startAt: at("15:00") }, prisma, NOW);
    await expect(rescheduleAppointment(pt.principal, a.id, at("15:00"), prisma, NOW)).rejects.toMatchObject({ code: "CONFLICT" });
    const orig = await prisma.appointment.findUniqueOrThrow({ where: { id: a.id } });
    expect(orig.status).toBe("AWAITING_NURSE_ACCEPTANCE");
    expect(await prisma.appointmentStatusHistory.count({ where: { appointmentId: a.id, toStatus: "RESCHEDULED" } })).toBe(0);
  });
});

describe("prescription authorization", () => {
  it("upload → staff verify → released to nurse; nurse is not asked before", async () => {
    const rx = await makeService({ slug: "med", requiresPrescription: true });
    await prisma.nurseServiceEligibility.create({ data: { nurseId: nurse.nurse.id, serviceId: rx.id, status: "APPROVED" } });
    const a = await createAppointment(pt.principal, { ...base(), serviceId: rx.id, startAt: at() }, prisma, NOW);
    expect(await prisma.notification.count({ where: { userId: nurse.principal.userId } })).toBe(0);
    await expect(startPrescriptionUpload(pt.principal, a.id, { kind: "PRESCRIPTION", mimeType: "text/html", sizeBytes: 10 }, prisma)).rejects.toMatchObject({ code: "VALIDATION" });
    const up = await startPrescriptionUpload(pt.principal, a.id, { kind: "PRESCRIPTION", mimeType: "application/pdf", sizeBytes: 1000 }, prisma);
    expect(up.upload.url).toContain("sig=");
    await expect(transitionAppointment(nurse.principal, a.id, "CONFIRMED", undefined, prisma, NOW)).rejects.toBeTruthy();
    await expect(decideAuthorization(pt.principal, up.document.id, "VERIFIED", undefined, prisma)).rejects.toMatchObject({ code: "FORBIDDEN" });
    const agent = await makeUser("+919000000003", ["SUPPORT_AGENT"]);
    await decideAuthorization(agent, up.document.id, "VERIFIED", undefined, prisma);
    expect((await prisma.appointment.findUniqueOrThrow({ where: { id: a.id } })).status).toBe("AWAITING_NURSE_ACCEPTANCE");
    expect(await prisma.notification.count({ where: { userId: nurse.principal.userId, templateKey: "appointment.requested" } })).toBeGreaterThan(0);
    await transitionAppointment(nurse.principal, a.id, "CONFIRMED", undefined, prisma, NOW);
  });
  it("rejection keeps the booking on hold", async () => {
    const rx = await makeService({ slug: "med2", requiresPrescription: true });
    await prisma.nurseServiceEligibility.create({ data: { nurseId: nurse.nurse.id, serviceId: rx.id, status: "APPROVED" } });
    const a = await createAppointment(pt.principal, { ...base(), serviceId: rx.id, startAt: at() }, prisma, NOW);
    const up = await startPrescriptionUpload(pt.principal, a.id, { kind: "PRESCRIPTION", mimeType: "image/png", sizeBytes: 1000 }, prisma);
    const admin = await makeUser("+919000000001", ["ADMIN"]);
    await decideAuthorization(admin, up.document.id, "REJECTED", "expired", prisma);
    expect((await prisma.appointment.findUniqueOrThrow({ where: { id: a.id } })).status).toBe("AWAITING_AUTHORIZATION");
  });
  it("receipt is for the patient only", async () => {
    const a = await createAppointment(pt.principal, { ...base(), startAt: at() }, prisma, NOW);
    expect((await receiptFor(pt.principal, a.id, prisma)).reference).toBe(a.reference);
    await expect(receiptFor(nurse.principal, a.id, prisma)).rejects.toMatchObject({ code: "FORBIDDEN" });
  });
});

async function stayFixture() {
  const partner = await makeUser("+919444444444", ["ACCOMMODATION_PARTNER"]);
  const pr = await prisma.accommodationPartner.create({ data: { userId: partner.userId, businessName: "P" } });
  const prop = await prisma.accommodationProperty.create({
    data: { partnerId: pr.id, name: "Near", description: "d", propertyType: "SERVICED_APARTMENT", address: "a", city: "Bengaluru", state: "Karnataka", pincode: "560001", latitude: 12.972, longitude: 77.64, bedrooms: 1, bathrooms: 1, maxGuests: 3, accessibility: [], minStayNights: 1, cancellationPolicy: "c", verificationStatus: "VERIFIED", units: { create: [{ label: "U1" }] }, rates: { create: { nightlyInPaise: 200000, depositInPaise: 50000, validFrom: new Date("2000-01-01") } } },
  });
  const h = await prisma.hospital.create({ data: { name: "H", address: "x", city: "Bengaluru", state: "Karnataka", pincode: "560001", latitude: 12.9719, longitude: 77.6412, dataSource: "t" } });
  return { partner, prop, h };
}

describe("accommodation payments & partner tools", () => {
  it("payment opens only after confirmation; capture records commission", async () => {
    const { partner, prop } = await stayFixture();
    const b = await requestStay(pt.principal, { propertyId: prop.id, checkIn: "2026-12-01", checkOut: "2026-12-04", guests: 1 }, prisma);
    await expect(createStayOrder(pt.principal, b.id, prisma)).rejects.toMatchObject({ code: "PRECONDITION_FAILED" });
    await partnerRespond(partner, b.id, "CONFIRMED", prisma);
    const o = await createStayOrder(pt.principal, b.id, prisma);
    expect(o.amountInPaise).toBe(600000 + 50000);
    await confirmPayment({ providerOrderId: o.providerOrderId, providerPaymentId: "p1", signature: payments.sign(o.providerOrderId, "p1") }, prisma);
    expect((await prisma.accommodationBooking.findUniqueOrThrow({ where: { id: b.id } })).paymentStatus).toBe("PAID");
    expect(await prisma.commission.count({ where: { sourceType: "ACCOMMODATION" } })).toBe(1);
  });
  it("blackouts and rates: owner only; blackout removes from search", async () => {
    const { partner, prop, h } = await stayFixture();
    const rival = await makeUser("+919555000001", ["ACCOMMODATION_PARTNER"]);
    await prisma.accommodationPartner.create({ data: { userId: rival.userId, businessName: "R" } });
    await expect(addBlackout(rival, prop.id, "2026-12-01", "2026-12-03", undefined, prisma)).rejects.toMatchObject({ code: "NOT_FOUND" });
    await expect(setRate(rival, prop.id, { nightlyInPaise: 1, extendedStayDiscountPct: 0, depositInPaise: 0, validFrom: "2026-01-01" }, prisma)).rejects.toMatchObject({ code: "NOT_FOUND" });
    await addBlackout(partner, prop.id, "2026-12-01", "2026-12-03", "repairs", prisma);
    expect((await searchStays(prisma, { hospitalId: h.id, checkIn: "2026-12-02", checkOut: "2026-12-04", guests: 1 })).results).toHaveLength(0);
  });
  it("partner check-in / check-out lifecycle", async () => {
    const { partner, prop } = await stayFixture();
    const b = await requestStay(pt.principal, { propertyId: prop.id, checkIn: "2026-12-01", checkOut: "2026-12-04", guests: 1 }, prisma);
    await expect(partnerStayTransition(partner, b.id, "CHECKED_IN", undefined, prisma)).rejects.toMatchObject({ code: "CONFLICT" });
    await partnerRespond(partner, b.id, "CONFIRMED", prisma);
    await partnerStayTransition(partner, b.id, "CHECKED_IN", undefined, prisma);
    await partnerStayTransition(partner, b.id, "COMPLETED", undefined, prisma);
  });
});

describe("settlements & reconciliation", () => {
  it("generates nurse settlements idempotently from completed paid visits", async () => {
    const a = await createAppointment(pt.principal, { ...base(), startAt: at() }, prisma, NOW);
    await prisma.appointment.update({ where: { id: a.id }, data: { status: "COMPLETED", paymentStatus: "PAID" } });
    const admin = await makeUser("+919000000001", ["ADMIN"]);
    expect((await generateSettlements(admin, new Date("2026-11-01"), new Date("2026-12-01"), prisma)).created).toBe(1);
    expect((await generateSettlements(admin, new Date("2026-11-01"), new Date("2026-12-01"), prisma)).created).toBe(0);
    const s = await prisma.partnerSettlement.findFirstOrThrow();
    expect(s.netInPaise).toBe(a.amountInPaise - a.commissionInPaise);
    expect(Array.isArray(await reconciliationReport(admin, prisma))).toBe(true);
    await expect(generateSettlements(pt.principal, new Date(), new Date(), prisma)).rejects.toMatchObject({ code: "FORBIDDEN" });
  });
});

describe("admin operations", () => {
  it("CSV export neutralises formula injection", () => {
    expect(toCsv([{ a: "=HYPERLINK(1)", b: 'x"y' }])).toBe('"a","b"\n"\'=HYPERLINK(1)","x""y"');
  });
  it("review moderation recalculates nurse rating", async () => {
    const a = await createAppointment(pt.principal, { ...base(), startAt: at() }, prisma, NOW);
    const r = await prisma.review.create({ data: { appointmentId: a.id, nurseId: nurse.nurse.id, rating: 1 } });
    const admin = await makeUser("+919000000001", ["ADMIN"]);
    await moderateReview(admin, r.id, "VISIBLE", prisma);
    expect((await prisma.nurseProfile.findUniqueOrThrow({ where: { id: nurse.nurse.id } })).ratingCount).toBe(1);
    await moderateReview(admin, r.id, "HIDDEN", prisma);
    expect((await prisma.nurseProfile.findUniqueOrThrow({ where: { id: nurse.nurse.id } })).ratingCount).toBe(0);
  });
  it("hospital partnership needs an agreement reference; merges deactivate the duplicate", async () => {
    const admin = await makeUser("+919000000001", ["ADMIN"]);
    const h1 = await prisma.hospital.create({ data: { name: "A", address: "x", city: "B", state: "K", pincode: "560001", latitude: 1, longitude: 1, dataSource: "t" } });
    const h2 = await prisma.hospital.create({ data: { name: "A dup", address: "x", city: "B", state: "K", pincode: "560001", latitude: 1, longitude: 1, dataSource: "t" } });
    await expect(updateHospital(admin, h1.id, { hasFormalPartnership: true }, prisma)).rejects.toMatchObject({ code: "VALIDATION" });
    await mergeHospitals(admin, h2.id, h1.id, prisma);
    expect(await prisma.hospital.findUniqueOrThrow({ where: { id: h2.id } })).toMatchObject({ isActive: false, mergedIntoId: h1.id });
  });
  it("suspicious-activity signals and retention run", async () => {
    const admin = await makeUser("+919000000001", ["ADMIN"]);
    expect(Array.isArray(await suspiciousActivity(admin, prisma))).toBe(true);
    await prisma.otpChallenge.create({ data: { phone: "+919999999999", codeHash: "x", expiresAt: new Date("2020-01-01"), createdAt: new Date("2020-01-01") } });
    expect((await applyRetention(prisma)).otp).toBe(1);
  });
});

describe("notifications & providers", () => {
  it("email is skipped without an address, sent with one; failures retry then FAIL", async () => {
    const email = new MockEmailProvider();
    let smsCalls = 0;
    setProviders({ email, sms: { name: "flaky", send: async () => { smsCalls++; return { ok: false, error: "down" }; } } });
    await notify(prisma, pt.principal.userId, "appointment.confirmed", { ref: "HN-1", when: "x" }, ["SMS", "EMAIL"]);
    await dispatchPending(prisma); // no email address yet → EMAIL skipped
    await prisma.user.update({ where: { id: pt.principal.userId }, data: { email: "a@example.com" } });
    await notify(prisma, pt.principal.userId, "appointment.confirmed", { ref: "HN-2", when: "x" }, ["EMAIL"]);
    for (let i = 0; i < 3; i++) await dispatchPending(prisma);
    const rows = await prisma.notification.findMany({ orderBy: { createdAt: "asc" } });
    expect(rows.find((r) => r.channel === "SMS")!.status).toBe("FAILED");
    expect(smsCalls).toBe(3);
    expect(email.outbox).toHaveLength(1);
    expect(rows.filter((r) => r.channel === "EMAIL").map((r) => r.status).sort()).toEqual(["SENT", "SKIPPED"]);
  });
  it("S3 presigner produces private, signed, short-lived URLs (no network)", async () => {
    const s3 = new S3StorageProvider({ bucket: "hn-private", region: "ap-south-1", accessKeyId: "AKIAEXAMPLE", secretAccessKey: "secret" });
    const up = await s3.presignUpload("credentials/n1/x.pdf", "application/pdf", 300);
    expect(up.url).toContain("hn-private");
    expect(up.url).toContain("X-Amz-Signature=");
    expect(up.url).toContain("X-Amz-Expires=300");
  });
  it("MSG91 maps provider errors to failures and uses the OTP template for codes", async () => {
    let sent: { template_id?: string } = {};
    const ok = new Msg91SmsProvider("k", "T_DEFAULT", "T_OTP", (async (_u: unknown, init: RequestInit) => { sent = JSON.parse(init.body as string); return new Response(JSON.stringify({ type: "success", message: "id1" })); }) as typeof fetch);
    expect((await ok.send("+919812345678", "123456 is your verification code.")).ok).toBe(true);
    expect(sent.template_id).toBe("T_OTP");
    const bad = new Msg91SmsProvider("k", "T", "O", (async () => new Response(JSON.stringify({ type: "error", message: "bad template" }), { status: 400 })) as typeof fetch);
    expect((await bad.send("+919812345678", "hello")).ok).toBe(false);
  });
  it("Google geocoding parses results and returns [] on failure", async () => {
    const g = new GoogleGeocodingProvider("k", (async () => new Response(JSON.stringify({ status: "OK", results: [{ formatted_address: "X, Bengaluru 560034", geometry: { location: { lat: 1, lng: 2 } }, address_components: [{ long_name: "560034", types: ["postal_code"] }, { long_name: "Bengaluru", types: ["locality"] }] }] }))) as typeof fetch);
    expect((await g.search("x"))[0]).toMatchObject({ lat: 1, lng: 2, pincode: "560034", city: "Bengaluru" });
    const down = new GoogleGeocodingProvider("k", (async () => new Response("", { status: 500 })) as typeof fetch);
    expect(await down.search("x")).toEqual([]);
  });
});
