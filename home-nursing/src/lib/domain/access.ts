import type { Db } from "../db";
import { AppError } from "../errors";
import type { Principal } from "../auth/session";

/** Patient-profile access: account holder, or linked caregiver with the needed right. */
export async function assertPatientAccess(db: Db, p: Principal, patientId: string, need: "book" | "records" = "book") {
  const patient = await db.patientProfile.findFirst({
    where: { id: patientId, deletedAt: null },
    include: { caregivers: { where: { caregiverUserId: p.userId } } },
  });
  if (!patient) throw new AppError("NOT_FOUND", "Patient not found");
  if (patient.accountUserId === p.userId) return patient;
  const link = patient.caregivers[0];
  if (link && (need === "book" ? link.canBook : link.canViewRecords)) return patient;
  throw new AppError("NOT_FOUND", "Patient not found"); // do not reveal existence
}

export async function nurseIdFor(db: Db, p: Principal) {
  const n = await db.nurseProfile.findUnique({ where: { userId: p.userId }, select: { id: true } });
  if (!n) throw new AppError("FORBIDDEN", "Nurse profile required");
  return n.id;
}
