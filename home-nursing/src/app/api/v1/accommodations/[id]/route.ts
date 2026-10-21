import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { AppError } from "@/lib/errors";

export const GET = route({}, async ({ params }) => {
  const p = await prisma.accommodationProperty.findFirst({
    where: { id: params.id!, isActive: true, verificationStatus: "VERIFIED" },
    include: { images: true, amenities: true, rates: { orderBy: { validFrom: "desc" }, take: 1 }, units: { select: { id: true } }, blackouts: true },
  });
  if (!p) throw new AppError("NOT_FOUND", "Property not found");
  const { partnerId: _omit, ...pub } = p;
  return pub;
});
