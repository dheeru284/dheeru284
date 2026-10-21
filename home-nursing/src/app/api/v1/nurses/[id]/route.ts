import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { AppError } from "@/lib/errors";

/** Public nurse profile: approved nurses only; no contact details, coordinates or documents. */
export const GET = route({}, async ({ params }) => {
  const n = await prisma.nurseProfile.findFirst({
    where: { id: params.id!, status: "APPROVED" },
    select: {
      id: true, displayName: true, gender: true, bio: true, languages: true, yearsExperience: true, ratingAvg: true, ratingCount: true, completedVisits: true, isDemo: true,
      qualifications: { where: { verificationStatus: "VERIFIED" }, select: { code: true } },
      registrations: { where: { status: "VERIFIED" }, select: { councilName: true, state: true } },
      serviceAreas: { select: { label: true } },
      eligibilities: { where: { status: "APPROVED" }, select: { service: { select: { id: true, name: true } }, priceInPaise: true } },
      reviews: { where: { moderationStatus: "VISIBLE" }, select: { rating: true, comment: true, createdAt: true }, orderBy: { createdAt: "desc" }, take: 20 },
    },
  });
  if (!n) throw new AppError("NOT_FOUND", "Nurse not found");
  return n;
});
