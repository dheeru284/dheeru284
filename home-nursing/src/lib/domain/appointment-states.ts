import type { AppointmentStatus } from "@prisma/client";

/** Statuses that hold a nurse's time slot. Must mirror the DB exclusion constraint's WHERE clause. */
export const ACTIVE_APPOINTMENT_STATUSES: AppointmentStatus[] = [
  "AWAITING_INFORMATION",
  "AWAITING_AUTHORIZATION",
  "AWAITING_NURSE_ACCEPTANCE",
  "CONFIRMED",
  "NURSE_EN_ROUTE",
  "NURSE_ARRIVED",
  "IN_PROGRESS",
  "COMPLETED",
  "RESCHEDULE_REQUESTED",
  "UNDER_REVIEW",
];

type Actor = "PATIENT" | "NURSE" | "ADMIN" | "SYSTEM";

/** Allowed transitions and who may perform them. */
export const TRANSITIONS: Partial<Record<AppointmentStatus, Partial<Record<AppointmentStatus, Actor[]>>>> = {
  AWAITING_AUTHORIZATION: { AWAITING_NURSE_ACCEPTANCE: ["ADMIN"], CANCELLED: ["PATIENT", "ADMIN"] },
  AWAITING_NURSE_ACCEPTANCE: { CONFIRMED: ["NURSE"], CANCELLED: ["PATIENT", "NURSE", "ADMIN", "SYSTEM"] },
  CONFIRMED: { NURSE_EN_ROUTE: ["NURSE"], CANCELLED: ["PATIENT", "NURSE", "ADMIN"], RESCHEDULE_REQUESTED: ["PATIENT", "NURSE"], NO_SHOW: ["NURSE", "ADMIN"] },
  NURSE_EN_ROUTE: { NURSE_ARRIVED: ["NURSE"], CANCELLED: ["NURSE", "ADMIN"] },
  NURSE_ARRIVED: { IN_PROGRESS: ["NURSE"], NO_SHOW: ["NURSE"] },
  IN_PROGRESS: { COMPLETED: ["NURSE"], UNDER_REVIEW: ["NURSE", "ADMIN"] },
  RESCHEDULE_REQUESTED: { RESCHEDULED: ["SYSTEM", "ADMIN"], CONFIRMED: ["PATIENT", "NURSE", "ADMIN"], CANCELLED: ["PATIENT", "ADMIN"] },
  COMPLETED: { UNDER_REVIEW: ["PATIENT", "ADMIN"] },
  UNDER_REVIEW: { COMPLETED: ["ADMIN"], CANCELLED: ["ADMIN"] },
};

export function canTransition(from: AppointmentStatus, to: AppointmentStatus, actor: Actor) {
  return TRANSITIONS[from]?.[to]?.includes(actor) ?? false;
}
