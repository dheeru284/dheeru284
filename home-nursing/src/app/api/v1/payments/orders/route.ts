import { z } from "zod";
import { route } from "@/lib/api";
import { createAppointmentOrder } from "@/lib/domain/payments";

export const POST = route({ permission: "appointment.book", body: z.object({ appointmentId: z.string() }) }, async ({ principal, body }) => createAppointmentOrder(principal!, body.appointmentId));
