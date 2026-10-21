import { beforeEach, describe, expect, it } from "vitest";
import { findMatches } from "@/lib/domain/matching";
import { decideDocument, setNurseStatus, startCredentialUpload, submitForVerification, sweepCredentialExpiry } from "@/lib/domain/credentials";
import { createPrivacyRequest, executeDeletion, exportMyData } from "@/lib/domain/privacy";
import { isFeatureEnabled } from "@/lib/domain/settings";
import { at, FakeRouting, makeNurse, makePatient, makeService, makeUser, NOW, prisma, resetDb, useFakes } from "./helpers";

beforeEach(async () => {
  await resetDb();
  useFakes(new FakeRouting({ "12.9701": 30 }));
});

describe("nurse verification workflow", () => {
  it("upload ≠ verified; approval requires verified mandatory credentials; decisions are audited", async () => {
    const svc = await makeService();
    const nurseUser = await makeUser("+919100000001", ["NURSE"]);
    const admin = await makeUser("+919000000001", ["ADMIN"]);
    const n = await prisma.nurseProfile.create({ data: { userId: nurseUser.userId, displayName: "N", gender: "FEMALE", languages: ["en"] } });
    await prisma.nurseRegistration.create({ data: { nurseId: n.id, councilName: "C", state: "KA", registrationNumber: "R1" } });
    const reg = await startCredentialUpload(nurseUser, { kind: "REGISTRATION_CERT", mimeType: "application/pdf", sizeBytes: 1000 }, prisma);
    const id = await startCredentialUpload(nurseUser, { kind: "ID_PROOF", mimeType: "image/png", sizeBytes: 1000 }, prisma);
    expect(reg.upload.url).toContain("sig=");
    expect(reg.document.status).toBe("PENDING");
    await submitForVerification(nurseUser, prisma);
    await expect(setNurseStatus(admin, n.id, "APPROVED", undefined, prisma)).rejects.toMatchObject({ code: "PRECONDITION_FAILED" });
    await decideDocument(admin, reg.document.id, "VERIFIED", "MANUAL_DOCUMENT_REVIEW", undefined, prisma);
    await decideDocument(admin, id.document.id, "VERIFIED", "MANUAL_DOCUMENT_REVIEW", undefined, prisma);
    await prisma.nurseRegistration.updateMany({ where: { nurseId: n.id }, data: { status: "VERIFIED" } });
    await setNurseStatus(admin, n.id, "APPROVED", undefined, prisma);
    expect(await prisma.credentialVerification.count()).toBe(2);
    expect(await prisma.auditLog.count({ where: { action: { startsWith: "credential." } } })).toBe(2);
    expect(await prisma.auditLog.count({ where: { action: "nurse.status.approved" } })).toBe(1);
    void svc;
  });
  it("patients cannot verify documents", async () => {
    const pt = await makeUser("+919100000002", ["PATIENT"]);
    await expect(decideDocument(pt, "x", "VERIFIED", "m", undefined, prisma)).rejects.toMatchObject({ code: "FORBIDDEN" });
  });
  it("expiry sweep marks credentials expired and removes the nurse from matching", async () => {
    const svc = await makeService();
    await makeNurse(svc.id, { lat: 12.9701, docExpires: new Date("2026-11-01T12:00:00Z") });
    await sweepCredentialExpiry(prisma, new Date("2026-11-01T13:00:00Z"));
    expect(await prisma.credentialDocument.count({ where: { status: "EXPIRED" } })).toBe(1);
    const r = await findMatches(prisma, { serviceId: svc.id, location: { lat: 12.95, lng: 77.6 }, startAt: at() }, NOW);
    expect(r.results).toHaveLength(0);
  });
});

describe("compliance gating", () => {
  it("an outstanding blocking item stops bookings in that state until satisfied or excepted", async () => {
    const svc = await makeService();
    await makeNurse(svc.id, { lat: 12.9701 });
    const item = await prisma.complianceItem.create({ data: { jurisdiction: "Karnataka", category: "x", responsibleParty: "PLATFORM", requirement: "test approval", requiredDocuments: [], blocksOperation: "NURSING_BOOKINGS" } });
    const req = { serviceId: svc.id, location: { lat: 12.95, lng: 77.6, state: "Karnataka" }, startAt: at() };
    await expect(findMatches(prisma, req, NOW)).rejects.toMatchObject({ code: "COMPLIANCE_BLOCKED" });
    await prisma.complianceItem.update({ where: { id: item.id }, data: { status: "EXCEPTION_RECORDED", exceptionNote: "documented" } });
    await expect(findMatches(prisma, req, NOW)).resolves.toBeTruthy();
  });
});

describe("feature flags", () => {
  it("medicine delivery stays disabled", async () => {
    await prisma.featureFlag.create({ data: { key: "medicine_delivery", description: "future" } });
    expect(await isFeatureEnabled(prisma, "medicine_delivery")).toBe(false);
  });
});

describe("privacy requests", () => {
  it("export returns only the requester's data; deletion pseudonymises and is audited", async () => {
    const a = await makePatient("+919200000001");
    await makePatient("+919200000002");
    const exp = await exportMyData(a.principal, prisma);
    expect(exp.user.patientProfiles).toHaveLength(1);
    expect(JSON.stringify(exp)).not.toContain("+919200000002");
    const req = await createPrivacyRequest(a.principal, "DELETION", undefined, prisma);
    const pt = await makeUser("+919200000003", ["PATIENT"]);
    await expect(executeDeletion(pt, req.id, prisma)).rejects.toMatchObject({ code: "FORBIDDEN" });
    const officer = await makeUser("+919200000004", ["COMPLIANCE_OFFICER"]);
    await executeDeletion(officer, req.id, prisma);
    const u = await prisma.user.findUniqueOrThrow({ where: { id: a.principal.userId } });
    expect(u.status).toBe("DELETED");
    expect(u.phone).not.toContain("9200000001");
    expect(await prisma.auditLog.count({ where: { action: "privacy.deletion.execute" } })).toBe(1);
  });
});
