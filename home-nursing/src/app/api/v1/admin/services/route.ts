import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { AppError } from "@/lib/errors";
import { audit } from "@/lib/domain/audit";

export const GET = route({ permission: "catalog.manage" }, async () => prisma.nursingService.findMany({ include: { category: true, protocols: true }, orderBy: { name: "asc" } }));

export const PATCH = route(
  { permission: "catalog.manage", body: z.object({ id: z.string(), isActive: z.boolean().optional(), basePriceInPaise: z.number().int().positive().optional(), durationMinutes: z.number().int().min(10).max(720).optional(), clinicalReviewApproved: z.boolean().optional(), clinicalReviewer: z.string().max(120).optional() }) },
  async ({ principal, body }) => {
    const svc = await prisma.nursingService.findUnique({ where: { id: body.id } });
    if (!svc) throw new AppError("NOT_FOUND", "Service not found");
    if (body.clinicalReviewApproved && !body.clinicalReviewer) throw new AppError("VALIDATION", "Record the reviewing clinician to approve a restricted service");
    const { id, clinicalReviewer, ...data } = body;
    const updated = await prisma.nursingService.update({ where: { id }, data });
    await audit(prisma, { actorUserId: principal!.userId, action: "catalog.update", entityType: "NursingService", entityId: id, metadata: { ...data, clinicalReviewer: clinicalReviewer ?? null } });
    return updated;
  },
);
