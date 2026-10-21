import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { nurseIdFor } from "@/lib/domain/access";

export const GET = route({ permission: "nurse.self" }, async ({ principal }) => {
  const nurseId = await nurseIdFor(prisma, principal!);
  const [visits, settlements] = await Promise.all([
    prisma.appointment.findMany({ where: { nurseId, status: "COMPLETED" }, select: { reference: true, startAt: true, amountInPaise: true, commissionInPaise: true, paymentStatus: true, service: { select: { name: true } } }, orderBy: { startAt: "desc" } }),
    prisma.partnerSettlement.findMany({ where: { nurseId }, orderBy: { periodStart: "desc" } }),
  ]);
  const totals = visits.reduce((t, v) => ({ gross: t.gross + v.amountInPaise, commission: t.commission + v.commissionInPaise, unpaidByPatient: t.unpaidByPatient + (v.paymentStatus === "PAID" ? 0 : v.amountInPaise) }), { gross: 0, commission: 0, unpaidByPatient: 0 });
  return { totals: { ...totals, net: totals.gross - totals.commission }, visits, settlements };
});
