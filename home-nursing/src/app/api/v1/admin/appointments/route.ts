import { pageParams, route } from "@/lib/api";
import { prisma } from "@/lib/db";

/** Booking management list for operations. No clinical notes or street addresses. */
export const GET = route({ permission: "appointment.view_ops" }, async ({ url }) => {
  const status = url.searchParams.get("status") ?? undefined, q = url.searchParams.get("q") ?? undefined;
  return prisma.appointment.findMany({
    where: { ...(status ? { status: status as never } : {}), ...(q ? { reference: { contains: q.toUpperCase() } } : {}) },
    select: { id: true, reference: true, status: true, startAt: true, amountInPaise: true, paymentStatus: true, estTravelMinutes: true, travelEstimateSource: true, service: { select: { name: true } }, nurse: { select: { displayName: true } }, address: { select: { city: true } } },
    orderBy: { startAt: "desc" },
    ...pageParams(url),
  });
});
