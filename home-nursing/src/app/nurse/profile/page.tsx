import { prisma } from "@/lib/db";
import { requirePage } from "@/lib/page-auth";
import { NurseOnboarding } from "./NurseOnboarding";

export const dynamic = "force-dynamic";

export default async function Page() {
  const p = await requirePage("nurse.self", "/nurse/profile");
  const [n, services] = await Promise.all([
    prisma.nurseProfile.findUnique({ where: { userId: p.userId }, include: { qualifications: true, registrations: true, documents: { select: { id: true, kind: true, status: true, expiresOn: true } }, eligibilities: true, serviceAreas: true, availability: true } }),
    prisma.nursingService.findMany({ where: { isActive: true }, select: { id: true, name: true, requiredQualifications: true, basePriceInPaise: true } }),
  ]);
  return <NurseOnboarding nurse={JSON.parse(JSON.stringify(n))} services={services} />;
}
