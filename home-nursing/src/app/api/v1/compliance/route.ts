import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { audit } from "@/lib/domain/audit";

const item = z.object({
  jurisdiction: z.string().min(2).max(10), category: z.string().max(60),
  responsibleParty: z.enum(["PLATFORM", "NURSE", "CLINICAL_ESTABLISHMENT", "LAB_PARTNER", "ACCOMMODATION", "PAYMENT_TECH"]),
  requirement: z.string().min(5).max(500),
  applicability: z.enum(["CONFIRMED", "POTENTIALLY_APPLICABLE", "NOT_APPLICABLE_AFTER_REVIEW", "PENDING_LEGAL_REVIEW"]),
  issuingAuthority: z.string().max(200).optional(), referenceUrl: z.string().url().optional(), requiredDocuments: z.array(z.string()).default([]),
  issueDate: z.string().optional(), renewalDate: z.string().optional(), reviewer: z.string().max(120).optional(), reviewDate: z.string().optional(),
  status: z.enum(["OPEN", "IN_PROGRESS", "SATISFIED", "EXCEPTION_RECORDED", "LAPSED"]).default("OPEN"),
  blocksOperation: z.enum(["NURSING_BOOKINGS", "ACCOMMODATION_BOOKINGS"]).nullable().optional(),
  exceptionNote: z.string().max(2000).optional(), notes: z.string().max(4000).optional(),
});

const dates = (b: Partial<z.infer<typeof item>>) => ({
  ...b,
  issueDate: b.issueDate ? new Date(b.issueDate) : undefined,
  renewalDate: b.renewalDate ? new Date(b.renewalDate) : undefined,
  reviewDate: b.reviewDate ? new Date(b.reviewDate) : undefined,
});

export const GET = route({ permission: "compliance.manage" }, async ({ url }) => {
  const j = url.searchParams.get("jurisdiction");
  return prisma.complianceItem.findMany({ where: j ? { jurisdiction: j } : {}, orderBy: [{ jurisdiction: "asc" }, { category: "asc" }] });
});

export const POST = route({ permission: "compliance.manage", body: item }, async ({ principal, body }) => {
  const c = await prisma.complianceItem.create({ data: dates(body) as never });
  await audit(prisma, { actorUserId: principal!.userId, action: "compliance.create", entityType: "ComplianceItem", entityId: c.id });
  return c;
});

export const PATCH = route({ permission: "compliance.manage", body: item.partial().extend({ id: z.string() }).refine((b) => b.status !== "EXCEPTION_RECORDED" || !!b.exceptionNote, "A documented exception note is required") }, async ({ principal, body }) => {
  const { id, ...rest } = body;
  const c = await prisma.complianceItem.update({ where: { id }, data: dates(rest) as never });
  await audit(prisma, { actorUserId: principal!.userId, action: "compliance.update", entityType: "ComplianceItem", entityId: id, metadata: { status: c.status, applicability: c.applicability } });
  return c;
});
