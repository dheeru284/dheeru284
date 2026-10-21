import { prisma } from "@/lib/db";
import { requirePage } from "@/lib/page-auth";
import { PartnerPortal } from "./PartnerPortal";

export const dynamic = "force-dynamic";

export default async function Page() {
  const p = await requirePage("partner.self", "/partner");
  const partner = await prisma.accommodationPartner.findUnique({ where: { userId: p.userId }, include: { properties: { include: { units: true, rates: { take: 1, orderBy: { validFrom: "desc" } } } } } });
  return <PartnerPortal partner={JSON.parse(JSON.stringify(partner))} />;
}
