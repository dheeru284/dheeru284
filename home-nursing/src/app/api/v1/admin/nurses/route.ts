import { pageParams, route } from "@/lib/api";
import { prisma } from "@/lib/db";

/** Verification queue. Returns credential metadata only; documents open via short-lived signed URLs. */
export const GET = route({ permission: "nurse.verify" }, async ({ url }) => {
  const status = url.searchParams.get("status") ?? "PENDING_VERIFICATION";
  return prisma.nurseProfile.findMany({
    where: { status: status as never },
    include: { registrations: true, qualifications: true, documents: { select: { id: true, kind: true, status: true, mimeType: true, expiresOn: true, uploadedAt: true, mandatory: true } }, eligibilities: { include: { service: { select: { name: true } } } }, user: { select: { phone: true } } },
    orderBy: { updatedAt: "asc" },
    ...pageParams(url),
  });
});
