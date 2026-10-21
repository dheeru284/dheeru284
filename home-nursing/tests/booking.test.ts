import { beforeEach, describe, expect, it } from "vitest";
import { createAppointment, createRecurring, getAppointmentFor, rescheduleAppointment, transitionAppointment, updateChecklist } from "@/lib/domain/appointments";
import { confirmPayment, createAppointmentOrder, handlePaymentWebhook } from "@/lib/domain/payments";
import { setNurseStatus } from "@/lib/domain/credentials";
import { createHmac } from "node:crypto";
import { at, FakeRouting, makeNurse, makePatient, makeService, makeUser, NOW, prisma, resetDb, useFakes } from "./helpers";

let payments: ReturnType<typeof useFakes>["payments"];
let svc: Awaited<ReturnType<typeof makeService>>;
let nurse: Awaited<ReturnType<typeof makeNurse>>;
let pt: Awaited<ReturnType<typeof makePatient>>;
const book = (time = "10:00", date = "2026-11-02", who = pt) => createAppointment(who.principal, { patientId: who.patient.id, nurseId: nurse.nurse.id, serviceId: svc.id, addressId: who.address.id, startAt: at(time, date) }, prisma, NOW);

beforeEach(async () => {
  await resetDb();
  ({ payments } = useFakes(new FakeRouting({ "12.9701": 30 })));
  svc = await makeService();
  nurse = await makeNurse(svc.id, { lat: 12.9701 });
  pt = await makePatient();
});

describe("appointment lifecycle", () => {
  it("create → accept → en route → arrive → start → checklist → complete", async () => {
    const a = await book();
    expect(a.status).toBe("AWAITING_NURSE_ACCEPTANCE");
    expect(a.reference).toMatch(/^HN-/);
    expect(a.commissionInPaise).toBe(7500); // 15% of ₹500
    const n = nurse.principal;
    await transitionAppointment(n, a.id, "CONFIRMED", undefined, prisma, NOW);
    await transitionAppointment(n, a.id, "NURSE_EN_ROUTE", undefined, prisma, NOW);
    await transitionAppointment(n, a.id, "NURSE_ARRIVED", undefined, prisma, NOW);
    await transitionAppointment(n, a.id, "IN_PROGRESS", undefined, prisma, NOW);
    await expect(transitionAppointment(n, a.id, "COMPLETED", undefined, prisma, NOW)).rejects.toMatchObject({ code: "PRECONDITION_FAILED" });
    await updateChecklist(n, a.id, "identity", true, prisma);
    await transitionAppointment(n, a.id, "COMPLETED", undefined, prisma, NOW);
    const hist = await prisma.appointmentStatusHistory.findMany({ where: { appointmentId: a.id } });
    expect(hist).toHaveLength(6);
    expect((await prisma.nurseProfile.findUniqueOrThrow({ where: { id: nurse.nurse.id } })).completedVisits).toBe(1);
    expect(await prisma.notification.count({ where: { userId: pt.principal.userId, templateKey: "appointment.completed" } })).toBeGreaterThan(0);
  });

  it("patient cannot accept on the nurse's behalf; nurse can reject", async () => {
    const a = await book();
    await expect(transitionAppointment(pt.principal, a.id, "CONFIRMED", undefined, prisma, NOW)).rejects.toMatchObject({ code: "CONFLICT" });
    await transitionAppointment(nurse.principal, a.id, "CANCELLED", "unavailable", prisma, NOW);
    expect(await prisma.notification.count({ where: { userId: pt.principal.userId, templateKey: "appointment.declined" } })).toBeGreaterThan(0);
  });

  it("late cancellation applies the configured fee", async () => {
    const a = await book();
    await transitionAppointment(nurse.principal, a.id, "CONFIRMED", undefined, prisma, NOW);
    const late = new Date(at().getTime() - 60 * 60_000);
    const r = await transitionAppointment(pt.principal, a.id, "CANCELLED", "plans changed", prisma, late);
    expect(r.cancellationFeePct).toBe(50);
  });

  it("rechecks credentials at booking time", async () => {
    const admin = await makeUser("+919000000001", ["ADMIN"]);
    await setNurseStatus(admin, nurse.nurse.id, "SUSPENDED", "test", prisma);
    await expect(book()).rejects.toMatchObject({ code: "PRECONDITION_FAILED" });
  });

  it("prescription-required services wait for authorization", async () => {
    const rx = await makeService({ slug: "med", requiresPrescription: true });
    await prisma.nurseServiceEligibility.create({ data: { nurseId: nurse.nurse.id, serviceId: rx.id, status: "APPROVED" } });
    const a = await createAppointment(pt.principal, { patientId: pt.patient.id, nurseId: nurse.nurse.id, serviceId: rx.id, addressId: pt.address.id, startAt: at() }, prisma, NOW);
    expect(a.status).toBe("AWAITING_AUTHORIZATION");
  });
});

describe("double booking", () => {
  it("sequential overlapping booking is rejected", async () => {
    await book("10:00");
    await expect(book("10:30")).rejects.toMatchObject({ code: "CONFLICT" });
  });
  it("travel buffer blocks back-to-back slots", async () => {
    await book("10:00"); // 10:00–11:00, blocks until 11:10
    await expect(book("11:15")).rejects.toMatchObject({ code: "CONFLICT" }); // needs 15-min travel buffer before → 11:00
    await expect(book("11:25")).resolves.toBeTruthy();
  });
  it("concurrent attempts: exactly one succeeds (DB exclusion constraint)", async () => {
    const others = await Promise.all([1, 2, 3, 4, 5].map((i) => makePatient(`+91922222222${i}`)));
    const results = await Promise.allSettled(others.map((o) => book("14:00", "2026-11-02", o)));
    expect(results.filter((r) => r.status === "fulfilled")).toHaveLength(1);
    for (const r of results.filter((r) => r.status === "rejected")) expect((r as PromiseRejectedResult).reason).toMatchObject({ code: "CONFLICT" });
  });
  it("cancelled slots can be rebooked", async () => {
    const a = await book();
    await transitionAppointment(pt.principal, a.id, "CANCELLED", undefined, prisma, NOW);
    await expect(book()).resolves.toBeTruthy();
  });
});

describe("reschedule & recurring", () => {
  it("reschedules to a free time and retires the original", async () => {
    const a = await book();
    const b = await rescheduleAppointment(pt.principal, a.id, at("15:00"), prisma, NOW);
    expect((await prisma.appointment.findUniqueOrThrow({ where: { id: a.id } })).status).toBe("RESCHEDULED");
    expect(b.startAt.toISOString()).toBe(at("15:00").toISOString());
  });
  it("failed reschedule restores the original", async () => {
    const a = await book();
    await expect(rescheduleAppointment(pt.principal, a.id, at("22:00"), prisma, NOW)).rejects.toBeTruthy();
    expect((await prisma.appointment.findUniqueOrThrow({ where: { id: a.id } })).status).toBe("AWAITING_NURSE_ACCEPTANCE");
  });
  it("recurring visits skip conflicting dates rather than bypassing availability", async () => {
    await book("10:00", "2026-11-04"); // occupies the 3rd occurrence
    const r = await createRecurring(pt.principal, { patientId: pt.patient.id, nurseId: nurse.nurse.id, serviceId: svc.id, addressId: pt.address.id, startAt: at("10:00", "2026-11-02") }, { everyDays: 1, count: 4 }, prisma, NOW);
    expect(r.created).toHaveLength(3);
    expect(r.skipped).toHaveLength(1);
  });
});

describe("data isolation", () => {
  it("another patient cannot view or book for someone else's profile", async () => {
    const a = await book();
    const other = await makePatient("+919333333333");
    await expect(getAppointmentFor(other.principal, a.id, prisma)).rejects.toMatchObject({ code: "NOT_FOUND" });
    await expect(createAppointment(other.principal, { patientId: pt.patient.id, nurseId: nurse.nurse.id, serviceId: svc.id, addressId: other.address.id, startAt: at("16:00") }, prisma, NOW)).rejects.toMatchObject({ code: "NOT_FOUND" });
  });
  it("nurse sees no street address or clinical notes before confirming", async () => {
    const a = await book();
    const before = await getAppointmentFor(nurse.principal, a.id, prisma);
    expect(JSON.stringify(before)).not.toContain("1 Test St");
    expect(JSON.stringify(before)).not.toContain("secret-note");
    await transitionAppointment(nurse.principal, a.id, "CONFIRMED", undefined, prisma, NOW);
    expect(JSON.stringify(await getAppointmentFor(nurse.principal, a.id, prisma))).toContain("1 Test St");
  });
  it("a different nurse cannot act on the appointment", async () => {
    const a = await book();
    const other = await makeNurse(svc.id, { lat: 12.9701 });
    await expect(transitionAppointment(other.principal, a.id, "CONFIRMED", undefined, prisma, NOW)).rejects.toBeTruthy();
  });
  it("admin ops view excludes clinical notes", async () => {
    const a = await book();
    const admin = await makeUser("+919000000001", ["ADMIN"]);
    expect(JSON.stringify(await getAppointmentFor(admin, a.id, prisma))).not.toContain("secret-note");
  });
});

describe("payments", () => {
  it("captures only with a valid server-verified signature; idempotent", async () => {
    const a = await book();
    const order = await createAppointmentOrder(pt.principal, a.id, prisma);
    await expect(confirmPayment({ providerOrderId: order.providerOrderId, providerPaymentId: "pay_1", signature: "forged" }, prisma)).rejects.toMatchObject({ code: "VALIDATION" });
    expect((await prisma.appointment.findUniqueOrThrow({ where: { id: a.id } })).paymentStatus).toBe("UNPAID");
    const sig = payments.sign(order.providerOrderId, "pay_1");
    await confirmPayment({ providerOrderId: order.providerOrderId, providerPaymentId: "pay_1", signature: sig }, prisma);
    await confirmPayment({ providerOrderId: order.providerOrderId, providerPaymentId: "pay_1", signature: sig }, prisma);
    expect((await prisma.appointment.findUniqueOrThrow({ where: { id: a.id } })).paymentStatus).toBe("PAID");
    expect(await prisma.commission.count()).toBe(1);
  });
  it("webhooks require a valid signature and are replay-safe", async () => {
    const a = await book();
    const order = await createAppointmentOrder(pt.principal, a.id, prisma);
    const body = JSON.stringify({ id: "evt_1", event: "payment.captured", payload: { payment: { entity: { id: "pay_9", order_id: order.providerOrderId } } } });
    await expect(handlePaymentWebhook(body, "bad", prisma)).rejects.toMatchObject({ code: "UNAUTHENTICATED" });
    const sig = createHmac("sha256", payments.secret).update(body).digest("hex");
    expect(await handlePaymentWebhook(body, sig, prisma)).toEqual({ duplicate: false });
    expect(await handlePaymentWebhook(body, sig, prisma)).toEqual({ duplicate: true });
  });
});
