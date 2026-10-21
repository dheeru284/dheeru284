import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { AppError } from "@/lib/errors";

export const POST = route(
  {
    permission: "property.manage",
    body: z.object({
      name: z.string().min(2).max(120), description: z.string().max(3000), propertyType: z.enum(["SERVICED_APARTMENT", "FURNISHED_APARTMENT", "GUEST_HOUSE"]),
      address: z.string(), city: z.string(), state: z.string(), pincode: z.string().regex(/^[1-9]\d{5}$/), latitude: z.number(), longitude: z.number(),
      bedrooms: z.number().int().min(0), bathrooms: z.number().int().min(0), maxGuests: z.number().int().min(1), units: z.number().int().min(1).max(200),
      accessibility: z.array(z.string()).default([]), amenities: z.array(z.string()).default([]), houseRules: z.string().optional(), minStayNights: z.number().int().min(1).default(1), cancellationPolicy: z.string(),
      nightlyInPaise: z.number().int().positive(), monthlyInPaise: z.number().int().positive().optional(), extendedStayDiscountPct: z.number().int().min(0).max(50).default(0), depositInPaise: z.number().int().min(0).default(0),
    }),
  },
  async ({ principal, body }) => {
    const partner = await prisma.accommodationPartner.findUnique({ where: { userId: principal!.userId } });
    if (!partner) throw new AppError("PRECONDITION_FAILED", "Complete partner registration first");
    const { units, amenities, nightlyInPaise, monthlyInPaise, extendedStayDiscountPct, depositInPaise, ...p } = body;
    // New properties start PENDING and are not listed until an admin verifies them.
    return prisma.accommodationProperty.create({
      data: {
        ...p, partnerId: partner.id, verificationStatus: "PENDING",
        units: { create: Array.from({ length: units }, (_, i) => ({ label: `Unit ${i + 1}` })) },
        amenities: { create: amenities.map((amenity) => ({ amenity })) },
        rates: { create: { nightlyInPaise, monthlyInPaise, extendedStayDiscountPct, depositInPaise, validFrom: new Date("2000-01-01") } },
      },
    });
  },
);
