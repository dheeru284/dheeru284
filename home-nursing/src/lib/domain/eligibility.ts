import type { CredentialDocument, NurseProfile, NurseQualification, NurseRegistration, NurseServiceEligibility, NursingService, User } from "@prisma/client";

export type NurseForGate = NurseProfile & {
  user: Pick<User, "status">;
  registrations: NurseRegistration[];
  documents: CredentialDocument[];
  qualifications: NurseQualification[];
  eligibilities: NurseServiceEligibility[];
};

export type GateResult = { ok: true } | { ok: false; reasons: string[] };

const valid = (expiresOn: Date | null, at: Date) => !expiresOn || expiresOn.getTime() > at.getTime();

/** Is the service itself bookable? Invasive/restricted services require clinical sign-off. */
export function serviceGate(s: NursingService, city?: string): GateResult {
  const reasons: string[] = [];
  if (!s.isActive) reasons.push("service_inactive");
  if (s.isInvasive && !s.clinicalReviewApproved) reasons.push("service_pending_clinical_review");
  if (city && s.allowedCities.length && !s.allowedCities.includes(city)) reasons.push("service_not_offered_in_city");
  return reasons.length ? { ok: false, reasons } : { ok: true };
}

/**
 * Can this nurse be booked for this service at this instant?
 * Uploading is not verifying: only VERIFIED, unexpired credentials count.
 */
export function nurseGate(n: NurseForGate, service: NursingService, at: Date): GateResult {
  const reasons: string[] = [];
  if (n.status !== "APPROVED") reasons.push(`nurse_${n.status.toLowerCase()}`);
  if (n.isPaused) reasons.push("nurse_paused");
  if (n.user.status !== "ACTIVE") reasons.push("account_inactive");

  const reg = n.registrations.find((r) => r.status === "VERIFIED" && valid(r.expiresOn, at));
  if (!reg) reasons.push("no_valid_verified_registration");

  const mandatory = n.documents.filter((d) => d.mandatory);
  if (mandatory.length === 0) reasons.push("no_mandatory_documents");
  for (const d of mandatory) {
    if (d.status !== "VERIFIED") reasons.push(`document_${d.kind.toLowerCase()}_${d.status.toLowerCase()}`);
    else if (!valid(d.expiresOn, at)) reasons.push(`document_${d.kind.toLowerCase()}_expired`);
  }

  const elig = n.eligibilities.find((e) => e.serviceId === service.id);
  if (elig?.status !== "APPROVED") reasons.push("service_not_approved_for_nurse");

  if (service.requiredQualifications.length) {
    const has = n.qualifications.some((q) => q.verificationStatus === "VERIFIED" && service.requiredQualifications.includes(q.code));
    if (!has) reasons.push("missing_required_verified_qualification");
  }
  return reasons.length ? { ok: false, reasons } : { ok: true };
}
