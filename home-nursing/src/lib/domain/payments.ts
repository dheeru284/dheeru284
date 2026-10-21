import { prisma, type Db } from "../db";
import { AppError } from "../errors";
import { logger } from "../logger";
import { providers } from "../providers";
import type { Principal } from "../auth/session";
import { assertPatientAccess } from "./access";
import { audit } from "./audit";
import { notify } from "./notifications";

/** Creates (or returns the existing) provider order for an appointment. Idempotent per appointment+amount. */
export async function createAppointmentOrder(p: Principal, appointmentId: string, db: Db = prisma) {
  const a = await db.appointment.findUnique({ where: { id: appointmentId } });
  if (!a) throw new AppError("NOT_FOUND", "Appointment not found");
  await assertPatientAccess(db, p, a.patientId, "book");
  if (a.paymentStatus === "PAID") throw new AppError("CONFLICT", "Already paid");
  const idempotencyKey = `appt:${a.id}:${a.amountInPaise}`;
  const existing = await db.payment.findUnique({ where: { idempotencyKey } });
  if (existing && existing.status === "CREATED") return { paymentId: existing.id, providerOrderId: existing.providerOrderId, amountInPaise: existing.amountInPaise, provider: existing.provider };
  const order = await providers().payments.createOrder({ amountInPaise: a.amountInPaise, receipt: a.reference });
  const pay = await db.payment.create({ data: { appointmentId: a.id, provider: providers().payments.name, providerOrderId: order.providerOrderId, amountInPaise: a.amountInPaise, idempotencyKey } });
  return { paymentId: pay.id, providerOrderId: order.providerOrderId, amountInPaise: a.amountInPaise, provider: pay.provider, checkout: order.checkout };
}

/** Order for a confirmed stay: total + refundable deposit. Payment is only requested after the partner confirms. */
export async function createStayOrder(p: Principal, bookingId: string, db: Db = prisma) {
  const b = await db.accommodationBooking.findFirst({ where: { id: bookingId, userId: p.userId } });
  if (!b) throw new AppError("NOT_FOUND", "Booking not found");
  if (b.status !== "CONFIRMED") throw new AppError("PRECONDITION_FAILED", "Payment opens once the property confirms your booking");
  if (b.paymentStatus === "PAID") throw new AppError("CONFLICT", "Already paid");
  const amount = b.totalInPaise + b.depositInPaise;
  const idempotencyKey = `stay:${b.id}:${amount}`;
  const existing = await db.payment.findUnique({ where: { idempotencyKey } });
  if (existing && existing.status === "CREATED") return { paymentId: existing.id, providerOrderId: existing.providerOrderId, amountInPaise: amount, provider: existing.provider };
  const order = await providers().payments.createOrder({ amountInPaise: amount, receipt: b.reference });
  const pay = await db.payment.create({ data: { accommodationBookingId: b.id, provider: providers().payments.name, providerOrderId: order.providerOrderId, amountInPaise: amount, idempotencyKey } });
  return { paymentId: pay.id, providerOrderId: order.providerOrderId, amountInPaise: amount, provider: pay.provider, checkout: order.checkout };
}

/** Client callback: verified with the provider signature server-side; the client's word alone is never trusted. */
export async function confirmPayment(input: { providerOrderId: string; providerPaymentId: string; signature: string }, db: Db = prisma) {
  const ok = providers().payments.verifyPaymentSignature({ orderId: input.providerOrderId, paymentId: input.providerPaymentId, signature: input.signature });
  if (!ok) {
    logger.warn("payment.signature_invalid", { order: input.providerOrderId });
    throw new AppError("VALIDATION", "Payment could not be verified");
  }
  return markCaptured(db, input.providerOrderId, input.providerPaymentId);
}

async function markCaptured(db: Db, providerOrderId: string, providerPaymentId: string) {
  const pay = await db.payment.findUnique({ where: { providerOrderId } });
  if (!pay) throw new AppError("NOT_FOUND", "Order not found");
  if (pay.status === "CAPTURED") return pay; // idempotent
  const updated = await db.payment.update({ where: { id: pay.id }, data: { status: "CAPTURED", providerPaymentId } });
  if (pay.appointmentId) {
    const a = await db.appointment.update({ where: { id: pay.appointmentId }, data: { paymentStatus: "PAID" } });
    await db.commission.upsert({ where: { sourceType_sourceId: { sourceType: "APPOINTMENT", sourceId: a.id } }, create: { sourceType: "APPOINTMENT", sourceId: a.id, amountInPaise: a.commissionInPaise }, update: {} });
    await notify(db, a.bookedByUserId, "payment.status", { ref: a.reference, status: "received" }, ["IN_APP"]);
  }
  if (pay.accommodationBookingId) {
    const b = await db.accommodationBooking.update({ where: { id: pay.accommodationBookingId }, data: { paymentStatus: "PAID" } });
    await db.commission.upsert({ where: { sourceType_sourceId: { sourceType: "ACCOMMODATION", sourceId: b.id } }, create: { sourceType: "ACCOMMODATION", sourceId: b.id, amountInPaise: b.commissionInPaise }, update: {} });
    await notify(db, b.userId, "payment.status", { ref: b.reference, status: "received" }, ["IN_APP"]);
  }
  return updated;
}

/** Signed webhook handler; replayed events are ignored via WebhookEvent primary key. */
export async function handlePaymentWebhook(rawBody: string, signature: string | null, db: Db = prisma) {
  if (!providers().payments.verifyWebhook(rawBody, signature)) throw new AppError("UNAUTHENTICATED", "Invalid webhook signature");
  const evt = JSON.parse(rawBody) as { id?: string; event: string; payload?: { payment?: { entity?: { id: string; order_id: string } } } };
  const eventId = evt.id ?? `${evt.event}:${evt.payload?.payment?.entity?.id}`;
  const seen = await db.webhookEvent.findUnique({ where: { id: eventId } });
  if (seen) return { duplicate: true };
  await db.webhookEvent.create({ data: { id: eventId, provider: providers().payments.name, type: evt.event } });
  const ent = evt.payload?.payment?.entity;
  if (evt.event === "payment.captured" && ent) await markCaptured(db, ent.order_id, ent.id);
  if (evt.event === "payment.failed" && ent) await db.payment.updateMany({ where: { providerOrderId: ent.order_id, status: "CREATED" }, data: { status: "FAILED" } });
  return { duplicate: false };
}

export async function refundPayment(admin: Principal, paymentId: string, amountInPaise: number, reason: string, db: Db = prisma) {
  if (!admin.permissions.has("payments.manage")) throw new AppError("FORBIDDEN", "Not allowed");
  const pay = await db.payment.findUnique({ where: { id: paymentId }, include: { refunds: true } });
  if (!pay || pay.status !== "CAPTURED" || !pay.providerPaymentId) throw new AppError("PRECONDITION_FAILED", "Only captured payments can be refunded");
  const already = pay.refunds.filter((r) => r.status !== "FAILED").reduce((s, r) => s + r.amountInPaise, 0);
  if (amountInPaise <= 0 || already + amountInPaise > pay.amountInPaise) throw new AppError("VALIDATION", "Refund exceeds the captured amount");
  const r = await providers().payments.refund({ paymentId: pay.providerPaymentId, amountInPaise });
  const refund = await db.refund.create({ data: { paymentId, amountInPaise, reason, status: "PROCESSED", providerRefundId: r.providerRefundId } });
  const refundState = already + amountInPaise === pay.amountInPaise ? "REFUNDED" : "PARTIALLY_REFUNDED";
  if (pay.appointmentId) await db.appointment.update({ where: { id: pay.appointmentId }, data: { paymentStatus: refundState } });
  if (pay.accommodationBookingId) await db.accommodationBooking.update({ where: { id: pay.accommodationBookingId }, data: { paymentStatus: refundState } });
  await audit(db, { actorUserId: admin.userId, action: "payment.refund", entityType: "Payment", entityId: paymentId, metadata: { amountInPaise, reason } });
  return refund;
}

/**
 * Period settlements for nurses (completed, paid visits) and partners (completed, paid stays).
 * Creates PENDING records only; actual payouts happen through the payment provider's payout product after finance review.
 * Idempotent per payee+period.
 */
export async function generateSettlements(admin: Principal, periodStart: Date, periodEnd: Date, db: Db = prisma) {
  if (!admin.permissions.has("payments.manage")) throw new AppError("FORBIDDEN", "Not allowed");
  const appts = await db.appointment.findMany({ where: { status: "COMPLETED", paymentStatus: "PAID", startAt: { gte: periodStart, lt: periodEnd } } });
  const stays = await db.accommodationBooking.findMany({ where: { status: "COMPLETED", paymentStatus: "PAID", checkOut: { gte: periodStart, lt: periodEnd } }, include: { unit: { include: { property: true } } } });
  const byNurse = new Map<string, { gross: number; commission: number }>();
  for (const a of appts) { const x = byNurse.get(a.nurseId) ?? { gross: 0, commission: 0 }; x.gross += a.amountInPaise; x.commission += a.commissionInPaise; byNurse.set(a.nurseId, x); }
  const byPartner = new Map<string, { gross: number; commission: number }>();
  for (const s of stays) { const k = s.unit.property.partnerId; const x = byPartner.get(k) ?? { gross: 0, commission: 0 }; x.gross += s.totalInPaise; x.commission += s.commissionInPaise; byPartner.set(k, x); }
  let created = 0;
  const upsert = async (who: { nurseId?: string; partnerId?: string }, v: { gross: number; commission: number }) => {
    const exists = await db.partnerSettlement.findFirst({ where: { ...who, periodStart, periodEnd } });
    if (exists) return;
    await db.partnerSettlement.create({ data: { ...who, periodStart, periodEnd, grossInPaise: v.gross, commissionInPaise: v.commission, netInPaise: v.gross - v.commission } });
    created++;
  };
  for (const [nurseId, v] of byNurse) await upsert({ nurseId }, v);
  for (const [partnerId, v] of byPartner) await upsert({ partnerId }, v);
  await audit(db, { actorUserId: admin.userId, action: "settlement.generate", entityType: "PartnerSettlement", metadata: { periodStart: periodStart.toISOString(), periodEnd: periodEnd.toISOString(), created } });
  return { created };
}

export async function markSettlementPaid(admin: Principal, id: string, payoutRef: string, db: Db = prisma) {
  if (!admin.permissions.has("payments.manage")) throw new AppError("FORBIDDEN", "Not allowed");
  const r = await db.partnerSettlement.updateMany({ where: { id, status: "PENDING" }, data: { status: "PAID" } });
  if (r.count !== 1) throw new AppError("NOT_FOUND", "Pending settlement not found");
  await audit(db, { actorUserId: admin.userId, action: "settlement.paid", entityType: "PartnerSettlement", entityId: id, metadata: { payoutRef } });
}

/** Reconciliation: captured payments vs. booking state, flagged for finance. */
export async function reconciliationReport(admin: Principal, db: Db = prisma) {
  if (!admin.permissions.has("payments.manage")) throw new AppError("FORBIDDEN", "Not allowed");
  const pays = await db.payment.findMany({ include: { refunds: true, appointment: { select: { reference: true, paymentStatus: true } } }, orderBy: { createdAt: "desc" }, take: 500 });
  return pays.map((p) => {
    const refunded = p.refunds.filter((r) => r.status !== "FAILED").reduce((s, r) => s + r.amountInPaise, 0);
    const issues: string[] = [];
    if (p.status === "CAPTURED" && p.appointment && !["PAID", "REFUNDED", "PARTIALLY_REFUNDED"].includes(p.appointment.paymentStatus)) issues.push("captured_but_booking_unpaid");
    if (p.status === "CREATED" && Date.now() - p.createdAt.getTime() > 86_400_000) issues.push("stale_unpaid_order");
    if (refunded > p.amountInPaise) issues.push("over_refunded");
    return { id: p.id, provider: p.provider, providerOrderId: p.providerOrderId, providerPaymentId: p.providerPaymentId, amountInPaise: p.amountInPaise, refundedInPaise: refunded, status: p.status, booking: p.appointment?.reference ?? p.accommodationBookingId, createdAt: p.createdAt, issues };
  });
}
