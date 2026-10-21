import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { findMatches } from "@/lib/domain/matching";
import { rateLimit } from "@/lib/rate-limit";
import { zonedToUtc } from "@/lib/time";

export const POST = route(
  {
    permission: "authenticated",
    body: z.object({
      serviceId: z.string(),
      addressId: z.string(),
      date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
      time: z.string().regex(/^\d{2}:\d{2}$/),
      genderPreference: z.enum(["FEMALE", "MALE"]).optional(),
      languages: z.array(z.string()).max(5).optional(),
      requestExpandedLimit: z.boolean().optional(),
    }),
  },
  async ({ principal, body }) => {
    await rateLimit(prisma, `match:${principal!.userId}`, 60, 3600);
    const addr = await prisma.patientAddress.findFirst({ where: { id: body.addressId, userId: principal!.userId, deletedAt: null } });
    if (!addr) return Response.json({ error: { code: "NOT_FOUND", message: "Address not found" } }, { status: 404 });
    return findMatches(prisma, {
      serviceId: body.serviceId,
      location: { lat: addr.latitude, lng: addr.longitude, city: addr.city, state: addr.state },
      startAt: zonedToUtc(body.date, body.time),
      genderPreference: body.genderPreference,
      languages: body.languages,
      requestExpandedLimit: body.requestExpandedLimit,
    });
  },
);
