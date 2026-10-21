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
  if (pay.appointmentId) await db.appointment.update({ where: { id: pay.appointmentId }, data: { paymentStatus: already + amountInPaise === pay.amountInPaise ? "REFUNDED" : "PARTIALLY_REFUNDED" } });
  await audit(db, { actorUserId: admin.userId, action: "payment.refund", entityType: "Payment", entityId: paymentId, metadata: { amountInPaise, reason } });
  return refund;
}
