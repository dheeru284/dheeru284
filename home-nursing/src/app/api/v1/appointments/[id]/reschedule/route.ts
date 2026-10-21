import { z } from "zod";
import { route } from "@/lib/api";
import { rescheduleAppointment } from "@/lib/domain/appointments";
import { zonedToUtc } from "@/lib/time";

export const POST = route({ permission: "appointment.book", body: z.object({ date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/), time: z.string().regex(/^\d{2}:\d{2}$/) }) }, async ({ principal, params, body }) =>
  rescheduleAppointment(principal!, params.id!, zonedToUtc(body.date, body.time)),
);
