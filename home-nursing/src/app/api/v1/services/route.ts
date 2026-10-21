import { route } from "@/lib/api";
import { prisma } from "@/lib/db";

export const GET = route({}, async () => {
  const services = await prisma.nursingService.findMany({ where: { isActive: true }, include: { category: true, requirements: true }, orderBy: { name: "asc" } });
  // Restricted services pending clinical review are not offered.
  return services.filter((s) => !s.isInvasive || s.clinicalReviewApproved);
});
