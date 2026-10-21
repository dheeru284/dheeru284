import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { nurseIdFor } from "@/lib/domain/access";

/** Nurse requests to offer a service; an admin must approve it against verified qualifications. */
export const POST = route({ permission: "nurse.self", body: z.object({ serviceId: z.string(), priceInPaise: z.number().int().min(0).max(10_000_000).optional() }) }, async ({ principal, body }) => {
  const nurseId = await nurseIdFor(prisma, principal!);
  return prisma.nurseServiceEligibility.upsert({
    where: { nurseId_serviceId: { nurseId, serviceId: body.serviceId } },
    create: { nurseId, serviceId: body.serviceId, priceInPaise: body.priceInPaise, status: "PENDING" },
    update: { priceInPaise: body.priceInPaise },
  });
});
