import { prisma, type Db } from "../db";
import { AppError } from "../errors";
import type { Principal } from "../auth/session";
import { audit } from "./audit";
import { grantRole } from "../auth/session";
import type { RoleKey } from "@prisma/client";

const need = (p: Principal, perm: string) => {
  if (!p.permissions.has(perm)) throw new AppError("FORBIDDEN", "Not allowed");
};

// ───────── Users ─────────
export async function listUsers(admin: Principal, q: { search?: string; role?: RoleKey; take: number; skip: number }, db: Db = prisma) {
  need(admin, "users.manage");
  return db.user.findMany({
    where: {
      ...(q.search ? { OR: [{ phone: { contains: q.search } }, { fullName: { contains: q.search, mode: "insensitive" } }] } : {}),
      ...(q.role ? { roles: { some: { role: { key: q.role } } } } : {}),
    },
    // Directory fields only — no clinical data.
    select: { id: true, phone: true, fullName: true, email: true, status: true, createdAt: true, roles: { select: { role: { select: { key: true } } } } },
    orderBy: { createdAt: "desc" },
    take: q.take,
    skip: q.skip,
  });
}

export async function setUserStatus(admin: Principal, userId: string, status: "ACTIVE" | "SUSPENDED", reason: string, db: typeof prisma = prisma) {
  need(admin, "users.manage");
  if (userId === admin.userId) throw new AppError("VALIDATION", "You cannot change your own status");
  await db.$transaction([
    db.user.update({ where: { id: userId }, data: { status } }),
    ...(status === "SUSPENDED" ? [db.session.updateMany({ where: { userId, revokedAt: null }, data: { revokedAt: new Date() } })] : []),
  ]);
  await audit(db, { actorUserId: admin.userId, action: `user.${status.toLowerCase()}`, entityType: "User", entityId: userId, metadata: { reason } });
}

/** Staff roles can only be granted by an admin; every grant is audited. */
export async function assignRole(admin: Principal, userId: string, role: RoleKey, db: Db = prisma) {
  need(admin, "users.manage");
  if (!admin.roles.includes("ADMIN")) throw new AppError("FORBIDDEN", "Only administrators can grant roles");
  await grantRole(db, userId, role);
  await audit(db, { actorUserId: admin.userId, action: "user.role.grant", entityType: "User", entityId: userId, metadata: { role } });
}

// ───────── Hospitals ─────────
export async function updateHospital(admin: Principal, id: string, data: Record<string, unknown>, db: Db = prisma) {
  need(admin, "hospital.manage");
  if (data.hasFormalPartnership === true && !data.partnershipAgreementRef) throw new AppError("VALIDATION", "Record the agreement reference to mark a formal partnership");
  if (data.verificationStatus === "VERIFIED") data.lastVerifiedAt = new Date();
  const h = await db.hospital.update({ where: { id }, data });
  await audit(db, { actorUserId: admin.userId, action: "hospital.update", entityType: "Hospital", entityId: id, metadata: data as never });
  return h;
}

/** Merge duplicate directory entries: source is deactivated and points at the target; references follow. */
export async function mergeHospitals(admin: Principal, sourceId: string, targetId: string, db: typeof prisma = prisma) {
  need(admin, "hospital.manage");
  if (sourceId === targetId) throw new AppError("VALIDATION", "Choose two different hospitals");
  await db.$transaction([
    db.accommodationBooking.updateMany({ where: { hospitalId: sourceId }, data: { hospitalId: targetId } }),
    db.hospital.update({ where: { id: sourceId }, data: { isActive: false, mergedIntoId: targetId } }),
  ]);
  await audit(db, { actorUserId: admin.userId, action: "hospital.merge", entityType: "Hospital", entityId: sourceId, metadata: { into: targetId } });
}

// ───────── Reviews ─────────
export async function moderateReview(admin: Principal, reviewId: string, status: "VISIBLE" | "HIDDEN" | "FLAGGED", db: typeof prisma = prisma) {
  need(admin, "reviews.moderate");
  const r = await db.review.update({ where: { id: reviewId }, data: { moderationStatus: status } });
  const agg = await db.review.aggregate({ where: { nurseId: r.nurseId, moderationStatus: "VISIBLE" }, _avg: { rating: true }, _count: true });
  await db.nurseProfile.update({ where: { id: r.nurseId }, data: { ratingAvg: agg._avg.rating ?? 0, ratingCount: agg._count } });
  await audit(db, { actorUserId: admin.userId, action: "review.moderate", entityType: "Review", entityId: reviewId, metadata: { status } });
  return r;
}

// ───────── Reports (CSV) ─────────
const csvCell = (v: unknown) => {
  const s = v instanceof Date ? v.toISOString() : v == null ? "" : String(v);
  // Neutralise spreadsheet formula injection and quote everything.
  const safe = /^[=+\-@\t\r]/.test(s) ? `'${s}` : s;
  return `"${safe.replaceAll('"', '""')}"`;
};
export const toCsv = (rows: Record<string, unknown>[]) => (rows.length ? [Object.keys(rows[0]!).map(csvCell).join(","), ...rows.map((r) => Object.values(r).map(csvCell).join(","))].join("\n") : "");

export const REPORTS = ["appointments", "stays", "payments", "nurses", "complaints"] as const;
export type ReportKind = (typeof REPORTS)[number];

/** Operational exports. Contain no clinical notes, addresses or contact details beyond what operations need. */
export async function exportReport(admin: Principal, kind: ReportKind, from: Date, to: Date, db: Db = prisma) {
  need(admin, "reports.export");
  let rows: Record<string, unknown>[] = [];
  if (kind === "appointments")
    rows = (await db.appointment.findMany({ where: { startAt: { gte: from, lt: to } }, include: { service: { select: { name: true } }, address: { select: { city: true } } } })).map((a) => ({ reference: a.reference, service: a.service.name, city: a.address.city, startAt: a.startAt, status: a.status, amountInPaise: a.amountInPaise, commissionInPaise: a.commissionInPaise, paymentStatus: a.paymentStatus, travelMinutes: a.estTravelMinutes, travelSource: a.travelEstimateSource }));
  if (kind === "stays")
    rows = (await db.accommodationBooking.findMany({ where: { checkIn: { gte: from, lt: to } }, include: { unit: { include: { property: { select: { name: true, city: true } } } } } })).map((b) => ({ reference: b.reference, property: b.unit.property.name, city: b.unit.property.city, checkIn: b.checkIn, checkOut: b.checkOut, status: b.status, totalInPaise: b.totalInPaise, commissionInPaise: b.commissionInPaise, paymentStatus: b.paymentStatus }));
  if (kind === "payments")
    rows = (await db.payment.findMany({ where: { createdAt: { gte: from, lt: to } }, include: { refunds: true } })).map((p) => ({ id: p.id, provider: p.provider, providerOrderId: p.providerOrderId, providerPaymentId: p.providerPaymentId, amountInPaise: p.amountInPaise, status: p.status, refundedInPaise: p.refunds.reduce((s, r) => s + r.amountInPaise, 0), createdAt: p.createdAt }));
  if (kind === "nurses")
    rows = (await db.nurseProfile.findMany({ include: { serviceAreas: { select: { city: true } } } })).map((n) => ({ id: n.id, name: n.displayName, status: n.status, city: n.serviceAreas[0]?.city, completedVisits: n.completedVisits, ratingAvg: n.ratingAvg, ratingCount: n.ratingCount, isDemo: n.isDemo }));
  if (kind === "complaints")
    rows = (await db.complaint.findMany({ where: { createdAt: { gte: from, lt: to } } })).map((c) => ({ id: c.id, category: c.category, severity: c.severity, status: c.status, createdAt: c.createdAt, updatedAt: c.updatedAt }));
  await audit(db, { actorUserId: admin.userId, action: "report.export", entityType: "Report", entityId: kind, metadata: { from: from.toISOString(), to: to.toISOString(), rows: rows.length } });
  return toCsv(rows);
}

// ───────── Suspicious activity monitoring ─────────
/** Rule-based signals for staff review. Never auto-suspends; a human decides. */
export async function suspiciousActivity(admin: Principal, db: Db = prisma, now = new Date()) {
  need(admin, "complaint.manage");
  const since = new Date(now.getTime() - 7 * 86_400_000);
  const [cancels, otpAbuse, complaintsByNurse, noShows] = await Promise.all([
    db.appointment.groupBy({ by: ["bookedByUserId"], where: { status: "CANCELLED", updatedAt: { gte: since } }, _count: true, having: { bookedByUserId: { _count: { gte: 5 } } } }),
    db.otpChallenge.groupBy({ by: ["phone"], where: { createdAt: { gte: since }, attempts: { gte: 3 } }, _count: true, having: { phone: { _count: { gte: 3 } } } }),
    db.$queryRaw<{ nurseId: string; n: bigint }[]>`SELECT a."nurseId", COUNT(*) n FROM "Complaint" c JOIN "Appointment" a ON a.id = c."appointmentId" WHERE c."createdAt" >= ${since} GROUP BY a."nurseId" HAVING COUNT(*) >= 2`,
    db.appointment.groupBy({ by: ["nurseId"], where: { status: "NO_SHOW", updatedAt: { gte: since } }, _count: true, having: { nurseId: { _count: { gte: 3 } } } }),
  ]);
  return [
    ...cancels.map((c) => ({ kind: "frequent_cancellations", subject: c.bookedByUserId, count: c._count })),
    ...otpAbuse.map((o) => ({ kind: "repeated_failed_otp", subject: o.phone.slice(0, -4) + "****", count: o._count })),
    ...complaintsByNurse.map((c) => ({ kind: "multiple_complaints_against_nurse", subject: c.nurseId, count: Number(c.n) })),
    ...noShows.map((n) => ({ kind: "frequent_no_shows", subject: n.nurseId, count: n._count })),
  ];
}

// ───────── Data retention ─────────
/** Purges data past configured retention. Durations are placeholders pending legal advice; clinical/tax records are not touched here. */
export async function applyRetention(db: Db = prisma, now = new Date(), policy = { otpDays: 1, sessionDays: 30, notificationDays: 180, routeCache: true }) {
  const d = (days: number) => new Date(now.getTime() - days * 86_400_000);
  const [otp, sessions, notes] = await Promise.all([
    db.otpChallenge.deleteMany({ where: { createdAt: { lt: d(policy.otpDays) } } }),
    db.session.deleteMany({ where: { OR: [{ expiresAt: { lt: d(policy.sessionDays) } }, { revokedAt: { lt: d(policy.sessionDays) } }] } }),
    db.notification.deleteMany({ where: { createdAt: { lt: d(policy.notificationDays) } } }),
  ]);
  if (policy.routeCache) await db.routeCacheEntry.deleteMany({ where: { expiresAt: { lt: now } } });
  return { otp: otp.count, sessions: sessions.count, notifications: notes.count };
}
