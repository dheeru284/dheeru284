import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { requestStay } from "@/lib/domain/accommodation";

const date = z.string().regex(/^\d{4}-\d{2}-\d{2}$/);

export const GET = route({ permission: "accommodation.book" }, async ({ principal }) =>
  prisma.accommodationBooking.findMany({ where: { userId: principal!.userId }, include: { unit: { include: { property: { select: { name: true, city: true } } } } }, orderBy: { checkIn: "desc" } }),
);

export const POST = route(
  // guestNote is for logistics only; the UI warns not to include medical details.
  { permission: "accommodation.book", body: z.object({ propertyId: z.string(), checkIn: date, checkOut: date, guests: z.number().int().min(1).max(20), hospitalId: z.string().optional(), guestNote: z.string().max(500).optional() }) },
  async ({ principal, body }) => Response.json({ data: await requestStay(principal!, body) }, { status: 201 }),
);
