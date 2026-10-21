import { z } from "zod";
import { route } from "@/lib/api";
import { transitionAppointment } from "@/lib/domain/appointments";

const TARGETS = ["CONFIRMED", "NURSE_EN_ROUTE", "NURSE_ARRIVED", "IN_PROGRESS", "COMPLETED", "CANCELLED", "RESCHEDULE_REQUESTED", "NO_SHOW", "UNDER_REVIEW", "AWAITING_NURSE_ACCEPTANCE"] as const;

export const POST = route({ permission: "authenticated", body: z.object({ to: z.enum(TARGETS), note: z.string().max(500).optional() }) }, async ({ principal, params, body }) =>
  transitionAppointment(principal!, params.id!, body.to, body.note),
);
