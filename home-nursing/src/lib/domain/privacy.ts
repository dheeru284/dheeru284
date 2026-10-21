import { prisma, type Db } from "../db";
import { AppError } from "../errors";
import type { Principal } from "../auth/session";
import { audit } from "./audit";

export const PRIVACY_NOTICE_VERSION = "2026-10-draft-1"; // draft pending legal review

export async function recordConsent(p: Principal, purpose: string, patientId?: string, db: Db = prisma) {
  return db.patientConsent.create({ data: { userId: p.userId, patientId, purpose, noticeVersion: PRIVACY_NOTICE_VERSION } });
}

export async function withdrawConsent(p: Principal, consentId: string, db: Db = prisma) {
  const r = await db.patientConsent.updateMany({ where: { id: consentId, userId: p.userId, withdrawnAt: null }, data: { withdrawnAt: new Date() } });
  if (r.count !== 1) throw new AppError("NOT_FOUND", "Consent not found");
}

export async function createPrivacyRequest(p: Principal, kind: "ACCESS" | "CORRECTION" | "DELETION" | "CONSENT_WITHDRAWAL" | "GRIEVANCE", details: string | undefined, db: Db = prisma) {
  // Response window is a configurable placeholder; confirm against DPDP Rules with counsel.
  const req = await db.privacyRequest.create({ data: { userId: p.userId, kind, details, dueBy: new Date(Date.now() + 30 * 86_400_000) } });
  if (kind === "DELETION") await db.user.update({ where: { id: p.userId }, data: { status: "DELETION_REQUESTED" } });
  await audit(db, { actorUserId: p.userId, action: `privacy.request.${kind.toLowerCase()}`, entityType: "PrivacyRequest", entityId: req.id });
  return req;
}

/** Data export for an ACCESS request: the user's own records, nothing about other people. */
export async function exportMyData(p: Principal, db: Db = prisma) {
  const user = await db.user.findUniqueOrThrow({
    where: { id: p.userId },
    include: { patientProfiles: true, addresses: true, consents: true, accommodationBookings: true, privacyRequests: true, tickets: true },
  });
  const appointments = await db.appointment.findMany({ where: { bookedByUserId: p.userId }, include: { history: true, visit: true } });
  await audit(db, { actorUserId: p.userId, action: "privacy.export", entityType: "User", entityId: p.userId });
  return { generatedAt: new Date().toISOString(), user, appointments };
}

/**
 * Executes an approved deletion: pseudonymises identity fields. Records that must be retained
 * (e.g. clinical visit records, tax invoices) are kept per the retention policy — set by counsel.
 */
export async function executeDeletion(admin: Principal, requestId: string, db: typeof prisma = prisma) {
  if (!admin.permissions.has("privacy.manage")) throw new AppError("FORBIDDEN", "Not allowed");
  const req = await db.privacyRequest.findUnique({ where: { id: requestId } });
  if (!req || req.kind !== "DELETION" || req.status === "COMPLETED") throw new AppError("NOT_FOUND", "Open deletion request not found");
  await db.$transaction([
    db.user.update({ where: { id: req.userId }, data: { status: "DELETED", deletedAt: new Date(), fullName: null, email: null, phone: `deleted:${req.userId}` } }),
    db.session.updateMany({ where: { userId: req.userId }, data: { revokedAt: new Date() } }),
    db.patientAddress.updateMany({ where: { userId: req.userId }, data: { deletedAt: new Date(), line1: "[deleted]", building: null, landmark: null } }),
    db.privacyRequest.update({ where: { id: requestId }, data: { status: "COMPLETED", resolvedAt: new Date() } }),
  ]);
  await audit(db, { actorUserId: admin.userId, action: "privacy.deletion.execute", entityType: "User", entityId: req.userId });
}
