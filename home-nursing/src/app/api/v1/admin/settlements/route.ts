import { z } from "zod";
import { pageParams, route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { generateSettlements, markSettlementPaid } from "@/lib/domain/payments";

export const GET = route({ permission: "payments.manage" }, async ({ url }) => prisma.partnerSettlement.findMany({ include: { partner: { select: { businessName: true } } }, orderBy: { createdAt: "desc" }, ...pageParams(url) }));

const d = z.string().regex(/^\d{4}-\d{2}-\d{2}$/);
export const POST = route({ permission: "payments.manage", body: z.union([z.object({ action: z.literal("generate"), periodStart: d, periodEnd: d }), z.object({ action: z.literal("mark_paid"), id: z.string(), payoutRef: z.string().min(3) })]) }, async ({ principal, body }) => {
  if (body.action === "generate") return generateSettlements(principal!, new Date(body.periodStart), new Date(body.periodEnd));
  await markSettlementPaid(principal!, body.id, body.payoutRef);
  return { ok: true };
});
