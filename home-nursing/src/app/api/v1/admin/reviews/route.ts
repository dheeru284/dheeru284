import { z } from "zod";
import { pageParams, route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { moderateReview } from "@/lib/domain/admin";

export const GET = route({ permission: "reviews.moderate" }, async ({ url }) =>
  prisma.review.findMany({ include: { nurse: { select: { displayName: true } } }, orderBy: { createdAt: "desc" }, ...pageParams(url) }),
);
export const PATCH = route({ permission: "reviews.moderate", body: z.object({ id: z.string(), status: z.enum(["VISIBLE", "HIDDEN", "FLAGGED"]) }) }, async ({ principal, body }) => moderateReview(principal!, body.id, body.status));
