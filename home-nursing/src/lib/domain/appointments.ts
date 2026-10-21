import { randomBytes } from "node:crypto";
import { Prisma, type AppointmentStatus } from "@prisma/client";
import { prisma, type Db } from "../db";
import { AppError } from "../errors";
import { haversineKm } from "../geo";
import { providers } from "../providers";
import type { Principal } from "../auth/session";
import { addMinutes, formatInTz } from "../time";
import { assertPatientAccess, nurseIdFor } from "./access";
import { ACTIVE_APPOINTMENT_STATUSES, canTransition } from "./appointment-states";
import { audit } from "./audit";
import { blockWindow, isAvailable } from "./availability";
import { assertOperationAllowed } from "./compliance";
import { nurseGate, serviceGate } from "./eligibility";
import { departureFor } from "./matching";
import { notify } from "./notifications";
import { getSetting } from "./settings";

export const newReference = (prefix: string) => `${prefix}-${randomBytes(4).toString("hex").toUpperCase()}`;

export type CreateAppointmentInput = { patientId: string; nurseId: string; serviceId: string; addressId: string; startAt: Date; patientNotes?: string; recurrenceGroupId?: string };

const isExclusionViolation = (e: unknown) =>
  (e instanceof Prisma.PrismaClientKnownRequestError && /appointment_no_nurse_overlap|23P01/.test(JSON.stringify(e.meta ?? {}) + e.message)) ||
  (e instanceof Prisma.PrismaClientUnknownRequestError && /appointment_no_nurse_overlap|23P01/.test(e.message)) ||
  (e instanceof Error && /appointment_no_nurse_overlap|exclusion constraint/.test(e.message));

const isDeadlock = (e: unknown) => e instanceof Error && /40P01|deadlock detected/.test(e.message);

/**
 * Creates an appointment after RE-validating everything the search showed (Step 9).
 * Double booking is prevented by the Postgres exclusion constraint, not just this check.
 */
export async function createAppointment(p: Principal, input: CreateAppointmentInput, db: typeof prisma = prisma, now = new Date()) {
  const s = await getSetting(db, "matching");
  const commerce = await getSetting(db, "commerce");
  await assertPatientAccess(db, p, input.patientId, "book");
  const address = await db.patientAddress.findFirst({ where: { id: input.addressId, userId: p.userId, deletedAt: null } });
  if (!address) throw new AppError("NOT_FOUND", "Address not found");
  await assertOperationAllowed(db, "NURSING_BOOKINGS", address.state);

  const service = await db.nursingService.findUnique({ where: { id: input.serviceId } });
  if (!service) throw new AppError("NOT_FOUND", "Service not found");
  const sg = serviceGate(service, address.city);
  if (!sg.ok) throw new AppError("PRECONDITION_FAILED", "Service not bookable", sg.reasons);
  if (input.startAt.getTime() < now.getTime() + s.bookingCutoffMinutes * 60_000) throw new AppError("VALIDATION", "Appointment is too soon to book");

  const { endAt, blockStart, blockEnd } = blockWindow(input.startAt, service.durationMinutes, s);
  const nurse = await db.nurseProfile.findUnique({
    where: { id: input.nurseId },
    include: {
      user: { select: { status: true } }, registrations: true, documents: true, qualifications: true, eligibilities: true, serviceAreas: true, availability: true,
      exceptions: { where: { endsAt: { gt: blockStart }, startsAt: { lt: blockEnd } } },
      appointments: { where: { status: { in: ACTIVE_APPOINTMENT_STATUSES }, blockEnd: { gt: blockStart }, blockStart: { lt: blockEnd } }, select: { blockStart: true, blockEnd: true } },
    },
  });
  if (!nurse) throw new AppError("NOT_FOUND", "Nurse not found");
  const gate = nurseGate(nurse, service, input.startAt);
  if (!gate.ok) throw new AppError("PRECONDITION_FAILED", "This nurse cannot currently be booked for this service", gate.reasons);
  const av = isAvailable(input.startAt, endAt, { blockStart, blockEnd }, nurse.availability, nurse.exceptions, nurse.appointments);
  if (!av.ok) throw new AppError("CONFLICT", "The nurse is no longer available at this time", av.reason);

  const area = nurse.serviceAreas.find((a) => a.isPrimary) ?? nurse.serviceAreas[0];
  if (!area) throw new AppError("PRECONDITION_FAILED", "Nurse has no service area");
  const origin = { lat: area.latitude, lng: area.longitude };
  const dest = { lat: address.latitude, lng: address.longitude };
  if (haversineKm(origin, dest) > s.fallbackRadiusKm) throw new AppError("PRECONDITION_FAILED", "Address is outside this nurse's coverage");
  let est = null;
  try { est = await providers().routing.estimate(origin, dest, departureFor(input.startAt, s)); } catch { est = null; }
  const limit = Math.min(s.maxTravelMinutes, area.maxTravelMinutes ?? s.maxTravelMinutes);
  if (!est && s.routingUnavailablePolicy === "EXCLUDE") throw new AppError("PROVIDER_UNAVAILABLE", "Travel time could not be estimated right now. Please try again shortly.");
  if (est && est.minutes > limit) throw new AppError("PRECONDITION_FAILED", `Nurse is beyond the ${limit}-minute travel limit`);

  const elig = nurse.eligibilities.find((e) => e.serviceId === service.id)!;
  const amount = (elig.priceInPaise ?? service.basePriceInPaise) + service.travelChargeInPaise;
  const commission = Math.round((amount * commerce.nursingCommissionPct) / 100) + commerce.nursingFixedFeeInPaise;
  const status: AppointmentStatus = service.requiresPrescription ? "AWAITING_AUTHORIZATION" : "AWAITING_NURSE_ACCEPTANCE";

  const insert = () => db.$transaction(async (tx) => {
      const a = await tx.appointment.create({
        data: {
          reference: newReference("HN"), patientId: input.patientId, bookedByUserId: p.userId, nurseId: nurse.id, serviceId: service.id, addressId: address.id,
          startAt: input.startAt, endAt, blockStart, blockEnd, status, recurrenceGroupId: input.recurrenceGroupId,
          estTravelMinutes: est?.minutes, estDistanceKm: est?.distanceKm, travelEstimateSource: est ? est.provider : "UNAVAILABLE",
          amountInPaise: amount, commissionInPaise: commission, patientNotes: input.patientNotes,
        },
      });
      await tx.appointmentStatusHistory.create({ data: { appointmentId: a.id, toStatus: status, actorUserId: p.userId, note: "created" } });
      return a;
    });
  try {
    // Concurrent overlapping inserts can surface as a deadlock (40P01) from the exclusion check; retry once, then it reports as an exclusion violation.
    const appt = await insert().catch((e) => (isDeadlock(e) ? insert() : Promise.reject(e)));
    if (status === "AWAITING_NURSE_ACCEPTANCE") await notify(db, nurse.userId, "appointment.requested", { ref: appt.reference, when: formatInTz(appt.startAt) });
    return appt;
  } catch (e) {
    if (isExclusionViolation(e) || isDeadlock(e)) throw new AppError("CONFLICT", "This time slot was just taken. Please choose another time or nurse.");
    throw e;
  }
}

/** Recurring visits: each occurrence passes the full availability/eligibility check. Conflicting dates are skipped and reported, never forced. */
export async function createRecurring(p: Principal, base: CreateAppointmentInput, opts: { everyDays: number; count: number }, db: typeof prisma = prisma, now = new Date()) {
  if (opts.count < 1 || opts.count > 60 || opts.everyDays < 1 || opts.everyDays > 30) throw new AppError("VALIDATION", "Invalid recurrence");
  const groupId = newReference("RG");
  const created: string[] = [];
  const skipped: { startAt: string; reason: string }[] = [];
  for (let i = 0; i < opts.count; i++) {
    const startAt = addMinutes(base.startAt, i * opts.everyDays * 1440);
    try {
      const a = await createAppointment(p, { ...base, startAt, recurrenceGroupId: groupId }, db, now);
      created.push(a.id);
    } catch (e) {
      if (e instanceof AppError) skipped.push({ startAt: startAt.toISOString(), reason: e.message });
      else throw e;
    }
  }
  return { recurrenceGroupId: groupId, created, skipped };
}

type Actor = "PATIENT" | "NURSE" | "ADMIN";

async function actorFor(db: Db, p: Principal, apptId: string): Promise<{ actor: Actor; appt: Prisma.AppointmentGetPayload<{ include: { nurse: true; patient: true } }> }> {
  const appt = await db.appointment.findUnique({ where: { id: apptId }, include: { nurse: true, patient: true } });
  if (!appt) throw new AppError("NOT_FOUND", "Appointment not found");
  if (p.roles.includes("NURSE") && appt.nurse.userId === p.userId) return { actor: "NURSE", appt };
  if (p.permissions.has("appointment.view_ops")) return { actor: "ADMIN", appt };
  await assertPatientAccess(db, p, appt.patientId, "book");
  return { actor: "PATIENT", appt };
}

export async function transitionAppointment(p: Principal, apptId: string, to: AppointmentStatus, note?: string, db: typeof prisma = prisma, now = new Date()) {
  const { actor, appt } = await actorFor(db, p, apptId);
  if (!canTransition(appt.status, to, actor)) throw new AppError("CONFLICT", `Cannot move from ${appt.status} to ${to}`);

  let cancellationFeePct = 0;
  if (to === "CANCELLED" && actor === "PATIENT" && appt.status !== "AWAITING_NURSE_ACCEPTANCE") {
    const c = await getSetting(db, "commerce");
    const hoursBefore = (appt.startAt.getTime() - now.getTime()) / 3600_000;
    if (hoursBefore < c.freeCancellationHours) cancellationFeePct = c.lateCancellationFeePct;
  }

  const updated = await db.$transaction(async (tx) => {
    // Optimistic concurrency: only transition from the status we validated.
    const r = await tx.appointment.updateMany({ where: { id: apptId, status: appt.status }, data: { status: to, ...(to === "CANCELLED" ? { cancelReason: note ?? null } : {}) } });
    if (r.count !== 1) throw new AppError("CONFLICT", "Appointment changed; please refresh");
    await tx.appointmentStatusHistory.create({ data: { appointmentId: apptId, fromStatus: appt.status, toStatus: to, actorUserId: p.userId, note } });
    if (to === "NURSE_ARRIVED") await tx.visitRecord.upsert({ where: { appointmentId: apptId }, create: { appointmentId: apptId, arrivedAt: now }, update: { arrivedAt: now } });
    if (to === "IN_PROGRESS") await startVisit(tx, apptId, appt.serviceId, now);
    if (to === "COMPLETED") {
      const visit = await tx.visitRecord.findUnique({ where: { appointmentId: apptId }, include: { checklist: true } });
      const protocol = await tx.serviceProtocol.findFirst({ where: { serviceId: appt.serviceId, isActive: true } });
      const required = new Set(((protocol?.checklist ?? []) as { key: string; required?: boolean }[]).filter((i) => i.required).map((i) => i.key));
      const missing = visit?.checklist.filter((c) => required.has(c.itemKey) && !c.done).map((c) => c.itemKey) ?? [];
      if (missing.length) throw new AppError("PRECONDITION_FAILED", "Complete the required checklist items first", missing);
      await tx.visitRecord.update({ where: { appointmentId: apptId }, data: { completedAt: now } });
      await tx.nurseProfile.update({ where: { id: appt.nurseId }, data: { completedVisits: { increment: 1 } } });
    }
    return tx.appointment.findUniqueOrThrow({ where: { id: apptId } });
  });

  const when = formatInTz(appt.startAt);
  if (to === "CONFIRMED") await notify(db, appt.bookedByUserId, "appointment.confirmed", { ref: appt.reference, when });
  else if (to === "CANCELLED") {
    await notify(db, actor === "NURSE" ? appt.bookedByUserId : appt.nurse.userId, appt.status === "AWAITING_NURSE_ACCEPTANCE" && actor === "NURSE" ? "appointment.declined" : "appointment.cancelled", { ref: appt.reference });
  } else if (to === "COMPLETED") await notify(db, appt.bookedByUserId, "appointment.completed", { ref: appt.reference });
  else await notify(db, appt.bookedByUserId, "appointment.status", { ref: appt.reference, status: to.replaceAll("_", " ").toLowerCase() }, ["IN_APP"]);
  if (actor === "ADMIN") await audit(db, { actorUserId: p.userId, action: `appointment.${to.toLowerCase()}`, entityType: "Appointment", entityId: apptId });
  return { appointment: updated, cancellationFeePct };
}

async function startVisit(tx: Db, apptId: string, serviceId: string, now: Date) {
  const visit = await tx.visitRecord.upsert({ where: { appointmentId: apptId }, create: { appointmentId: apptId, startedAt: now }, update: { startedAt: now } });
  const protocol = await tx.serviceProtocol.findFirst({ where: { serviceId, isActive: true } });
  for (const item of (protocol?.checklist ?? []) as { key: string; label: string }[]) {
    await tx.visitChecklist.upsert({ where: { visitId_itemKey: { visitId: visit.id, itemKey: item.key } }, create: { visitId: visit.id, itemKey: item.key, label: item.label }, update: {} });
  }
}

/** Reschedule = create the new booking (fully re-validated) and retire the old one atomically. */
export async function rescheduleAppointment(p: Principal, apptId: string, newStartAt: Date, db: typeof prisma = prisma, now = new Date()) {
  const { actor, appt } = await actorFor(db, p, apptId);
  if (actor !== "PATIENT") throw new AppError("FORBIDDEN", "Only the patient account can reschedule");
  if (!["CONFIRMED", "AWAITING_NURSE_ACCEPTANCE", "RESCHEDULE_REQUESTED"].includes(appt.status)) throw new AppError("CONFLICT", "This appointment cannot be rescheduled");
  // Release the old slot first inside a transaction so an overlapping new time on the same nurse is allowed.
  const retired = await db.appointment.updateMany({ where: { id: apptId, status: appt.status }, data: { status: "RESCHEDULED" } });
  if (retired.count !== 1) throw new AppError("CONFLICT", "Appointment changed; please refresh");
  try {
    const fresh = await createAppointment(p, { patientId: appt.patientId, nurseId: appt.nurseId, serviceId: appt.serviceId, addressId: appt.addressId, startAt: newStartAt, patientNotes: appt.patientNotes ?? undefined }, db, now);
    await db.appointmentStatusHistory.create({ data: { appointmentId: apptId, fromStatus: appt.status, toStatus: "RESCHEDULED", actorUserId: p.userId, note: `rescheduled to ${fresh.reference}` } });
    return fresh;
  } catch (e) {
    await db.appointment.update({ where: { id: apptId }, data: { status: appt.status } }); // compensate
    throw e;
  }
}

/** Nurse-visible view: precise address only for the assigned nurse of an active booking. */
export async function getAppointmentFor(p: Principal, apptId: string, db: Db = prisma) {
  const { actor } = await actorFor(db, p, apptId);
  const full = await db.appointment.findUniqueOrThrow({
    where: { id: apptId },
    include: { service: true, address: true, history: { orderBy: { createdAt: "asc" } }, visit: { include: { checklist: true } }, patient: true, nurse: { include: { serviceAreas: true } } },
  });
  const revealAddress = actor !== "NURSE" || ["CONFIRMED", "NURSE_EN_ROUTE", "NURSE_ARRIVED", "IN_PROGRESS"].includes(full.status);
  return {
    viewer: actor,
    id: full.id, reference: full.reference, status: full.status, startAt: full.startAt, endAt: full.endAt,
    service: { id: full.service.id, name: full.service.name, durationMinutes: full.service.durationMinutes },
    nurse: { id: full.nurse.id, displayName: full.nurse.displayName, serviceArea: full.nurse.serviceAreas[0]?.label },
    patient:
      actor === "ADMIN"
        ? { id: full.patient.id, fullName: full.patient.fullName } // ops view: no clinical fields
        : actor === "NURSE" && !revealAddress
          ? { id: full.patient.id, fullName: full.patient.fullName.split(" ")[0] }
          : { id: full.patient.id, fullName: full.patient.fullName, allergies: full.patient.allergies, medicalNotes: full.patient.medicalNotes },
    address: revealAddress ? full.address : { city: full.address.city, locality: full.address.locality },
    travel: { minutes: full.estTravelMinutes, distanceKm: full.estDistanceKm, source: full.travelEstimateSource },
    amountInPaise: full.amountInPaise, paymentStatus: full.paymentStatus, history: full.history, visit: full.visit, patientNotes: full.patientNotes,
  };
}

export async function updateChecklist(p: Principal, apptId: string, itemKey: string, done: boolean, db: Db = prisma) {
  const nurseId = await nurseIdFor(db, p);
  const appt = await db.appointment.findFirst({ where: { id: apptId, nurseId, status: "IN_PROGRESS" }, include: { visit: true } });
  if (!appt?.visit) throw new AppError("NOT_FOUND", "Active visit not found");
  return db.visitChecklist.update({ where: { visitId_itemKey: { visitId: appt.visit.id, itemKey } }, data: { done } });
}

export async function recordVisitNotes(p: Principal, apptId: string, notes: string, observations: Record<string, number | string> | undefined, db: Db = prisma) {
  const nurseId = await nurseIdFor(db, p);
  const appt = await db.appointment.findFirst({ where: { id: apptId, nurseId, status: { in: ["IN_PROGRESS", "COMPLETED"] } } });
  if (!appt) throw new AppError("NOT_FOUND", "Visit not found");
  return db.visitRecord.update({ where: { appointmentId: apptId }, data: { notes, observations } });
}
