import { z } from "zod";
import { pageParams, route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { createAppointment, createRecurring } from "@/lib/domain/appointments";
import { zonedToUtc } from "@/lib/time";

export const GET = route({ permission: "patient.self" }, async ({ principal, url }) =>
  prisma.appointment.findMany({
    where: { patient: { OR: [{ accountUserId: principal!.userId }, { caregivers: { some: { caregiverUserId: principal!.userId, canBook: true } } }] } },
    include: { service: { select: { name: true } }, nurse: { select: { displayName: true } }, patient: { select: { fullName: true } } },
    orderBy: { startAt: "desc" },
    ...pageParams(url),
  }),
);

export const POST = route(
  {
    permission: "appointment.book",
    body: z.object({
      patientId: z.string(), nurseId: z.string(), serviceId: z.string(), addressId: z.string(),
      date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/), time: z.string().regex(/^\d{2}:\d{2}$/),
      patientNotes: z.string().max(1000).optional(),
      recurrence: z.object({ everyDays: z.number().int().min(1).max(30), count: z.number().int().min(2).max(60) }).optional(),
    }),
  },
  async ({ principal, body }) => {
    const base = { patientId: body.patientId, nurseId: body.nurseId, serviceId: body.serviceId, addressId: body.addressId, startAt: zonedToUtc(body.date, body.time), patientNotes: body.patientNotes };
    if (body.recurrence) return createRecurring(principal!, base, body.recurrence);
    return Response.json({ data: await createAppointment(principal!, base) }, { status: 201 });
  },
);
