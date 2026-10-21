import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { nurseIdFor } from "@/lib/domain/access";

/** Nurse's queue. Only city/locality is shown until a booking is confirmed. */
export const GET = route({ permission: "appointment.nurse" }, async ({ principal }) => {
  const nurseId = await nurseIdFor(prisma, principal!);
  const rows = await prisma.appointment.findMany({ where: { nurseId }, include: { service: { select: { name: true } }, address: { select: { city: true, locality: true } } }, orderBy: { startAt: "asc" } });
  return rows.map((a) => ({ id: a.id, reference: a.reference, status: a.status, startAt: a.startAt, endAt: a.endAt, service: a.service.name, area: `${a.address.locality ?? ""} ${a.address.city}`.trim(), amountInPaise: a.amountInPaise, commissionInPaise: a.commissionInPaise, travelMinutes: a.estTravelMinutes }));
});
