import type { CredentialStatus, NurseStatus } from "@prisma/client";
import { prisma, type Db } from "../db";
import { AppError } from "../errors";
import { providers } from "../providers";
import { ALLOWED_UPLOADS, MAX_UPLOAD_BYTES, newObjectKey } from "../providers/storage";
import type { Principal } from "../auth/session";
import { nurseIdFor } from "./access";
import { audit } from "./audit";
import { notify } from "./notifications";

export function validateUpload(category: keyof typeof ALLOWED_UPLOADS, mimeType: string, sizeBytes: number) {
  if (!ALLOWED_UPLOADS[category]!.includes(mimeType)) throw new AppError("VALIDATION", `File type ${mimeType} is not allowed`);
  if (!Number.isInteger(sizeBytes) || sizeBytes <= 0 || sizeBytes > MAX_UPLOAD_BYTES) throw new AppError("VALIDATION", "File must be between 1 byte and 10 MB");
}

/** Registers a document record (status PENDING) and returns a short-lived upload URL to private storage. */
export async function startCredentialUpload(p: Principal, input: { kind: string; mimeType: string; sizeBytes: number; expiresOn?: Date; mandatory?: boolean }, db: Db = prisma) {
  validateUpload("CREDENTIAL", input.mimeType, input.sizeBytes);
  const nurseId = await nurseIdFor(db, p);
  const key = newObjectKey(`credentials/${nurseId}`, input.mimeType);
  const doc = await db.credentialDocument.create({ data: { nurseId, kind: input.kind, storageKey: key, mimeType: input.mimeType, sizeBytes: input.sizeBytes, expiresOn: input.expiresOn, mandatory: input.mandatory ?? true } });
  const upload = await providers().storage.presignUpload(key, input.mimeType);
  return { document: { id: doc.id, kind: doc.kind, status: doc.status }, upload };
}

export async function submitForVerification(p: Principal, db: Db = prisma) {
  const nurseId = await nurseIdFor(db, p);
  const n = await db.nurseProfile.findUniqueOrThrow({ where: { id: nurseId }, include: { registrations: true, documents: true } });
  if (!n.registrations.length) throw new AppError("PRECONDITION_FAILED", "Add your nursing council registration first");
  if (!n.documents.some((d) => d.kind === "REGISTRATION_CERT")) throw new AppError("PRECONDITION_FAILED", "Upload your registration certificate");
  if (!n.documents.some((d) => d.kind === "ID_PROOF")) throw new AppError("PRECONDITION_FAILED", "Upload an identity document");
  if (!["DRAFT", "REJECTED"].includes(n.status)) throw new AppError("CONFLICT", "Profile is already submitted");
  return db.nurseProfile.update({ where: { id: nurseId }, data: { status: "PENDING_VERIFICATION" } });
}

/** Every decision is recorded append-only in CredentialVerification and in the audit log. */
export async function decideDocument(admin: Principal, documentId: string, decision: CredentialStatus, method: string, notes: string | undefined, db: typeof prisma = prisma) {
  if (!admin.permissions.has("nurse.verify")) throw new AppError("FORBIDDEN", "Not allowed");
  const doc = await db.credentialDocument.findUnique({ where: { id: documentId } });
  if (!doc) throw new AppError("NOT_FOUND", "Document not found");
  await db.$transaction([
    db.credentialDocument.update({ where: { id: documentId }, data: { status: decision } }),
    db.credentialVerification.create({ data: { documentId, decision, reviewerUserId: admin.userId, method, notes } }),
  ]);
  await audit(db, { actorUserId: admin.userId, action: "credential.document.decide", entityType: "CredentialDocument", entityId: documentId, metadata: { decision, method } });
}

export async function decideRegistration(admin: Principal, registrationId: string, decision: CredentialStatus, method: string, notes: string | undefined, db: typeof prisma = prisma) {
  if (!admin.permissions.has("nurse.verify")) throw new AppError("FORBIDDEN", "Not allowed");
  await db.$transaction([
    db.nurseRegistration.update({ where: { id: registrationId }, data: { status: decision } }),
    db.credentialVerification.create({ data: { registrationId, decision, reviewerUserId: admin.userId, method, notes } }),
  ]);
  await audit(db, { actorUserId: admin.userId, action: "credential.registration.decide", entityType: "NurseRegistration", entityId: registrationId, metadata: { decision, method } });
}

/** Approve/reject/suspend/reactivate a nurse. Approval requires verified mandatory credentials. */
export async function setNurseStatus(admin: Principal, nurseId: string, status: NurseStatus, reason: string | undefined, db: typeof prisma = prisma) {
  const need = status === "SUSPENDED" ? "nurse.suspend" : "nurse.verify";
  if (!admin.permissions.has(need)) throw new AppError("FORBIDDEN", "Not allowed");
  const n = await db.nurseProfile.findUnique({ where: { id: nurseId }, include: { registrations: true, documents: true } });
  if (!n) throw new AppError("NOT_FOUND", "Nurse not found");
  if (status === "APPROVED") {
    const missing: string[] = [];
    if (!n.registrations.some((r) => r.status === "VERIFIED")) missing.push("verified_registration");
    const pending = n.documents.filter((d) => d.mandatory && d.status !== "VERIFIED");
    if (pending.length) missing.push(...pending.map((d) => `document_${d.kind}`));
    if (missing.length) throw new AppError("PRECONDITION_FAILED", "Mandatory credentials are not verified", missing);
  }
  const updated = await db.nurseProfile.update({ where: { id: nurseId }, data: { status, ...(status === "APPROVED" ? { approvedAt: new Date() } : {}) } });
  await audit(db, { actorUserId: admin.userId, action: `nurse.status.${status.toLowerCase()}`, entityType: "NurseProfile", entityId: nurseId, metadata: { from: n.status, reason: reason ?? null } });
  await notify(db, n.userId, "nurse.verification", { status: status.toLowerCase().replace("_", " ") });
  return updated;
}

export async function approveServiceEligibility(admin: Principal, nurseId: string, serviceId: string, db: Db = prisma) {
  if (!admin.permissions.has("nurse.verify")) throw new AppError("FORBIDDEN", "Not allowed");
  const service = await db.nursingService.findUniqueOrThrow({ where: { id: serviceId } });
  if (service.requiredQualifications.length) {
    const q = await db.nurseQualification.findFirst({ where: { nurseId, verificationStatus: "VERIFIED", code: { in: service.requiredQualifications } } });
    if (!q) throw new AppError("PRECONDITION_FAILED", "Nurse lacks a verified qualification required for this service");
  }
  const e = await db.nurseServiceEligibility.upsert({
    where: { nurseId_serviceId: { nurseId, serviceId } },
    create: { nurseId, serviceId, status: "APPROVED", approvedBy: admin.userId, approvedAt: new Date() },
    update: { status: "APPROVED", approvedBy: admin.userId, approvedAt: new Date() },
  });
  await audit(db, { actorUserId: admin.userId, action: "nurse.eligibility.approve", entityType: "NurseServiceEligibility", entityId: e.id });
  return e;
}

/** Scheduled job: mark expired credentials and warn about upcoming expiries. */
export async function sweepCredentialExpiry(db: Db = prisma, now = new Date(), warnDays = 30) {
  const expired = await db.credentialDocument.updateMany({ where: { status: "VERIFIED", expiresOn: { lte: now } }, data: { status: "EXPIRED" } });
  const regs = await db.nurseRegistration.updateMany({ where: { status: "VERIFIED", expiresOn: { lte: now } }, data: { status: "EXPIRED" } });
  const soon = await db.credentialDocument.findMany({ where: { status: "VERIFIED", expiresOn: { gt: now, lte: new Date(now.getTime() + warnDays * 86_400_000) } }, include: { nurse: true } });
  for (const d of soon) await notify(db, d.nurse.userId, "credential.expiring", { date: d.expiresOn!.toISOString().slice(0, 10) });
  return { expiredDocuments: expired.count, expiredRegistrations: regs.count, warned: soon.length };
}
