import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { AppError } from "@/lib/errors";
import { searchStays } from "@/lib/domain/accommodation";

export const GET = route({}, async ({ url }) => {
  const g = (k: string) => url.searchParams.get(k) ?? undefined;
  const hospitalId = g("hospitalId"), checkIn = g("checkIn"), checkOut = g("checkOut");
  if (!hospitalId || !checkIn || !checkOut) throw new AppError("VALIDATION", "hospitalId, checkIn and checkOut are required");
  const list = (k: string) => g(k)?.split(",").filter(Boolean);
  return searchStays(prisma, {
    hospitalId, checkIn, checkOut, guests: Number(g("guests") ?? 1),
    maxNightlyInPaise: g("maxNightly") ? Number(g("maxNightly")) * 100 : undefined,
    amenities: list("amenities"), accessibility: list("accessibility"), propertyType: g("propertyType"), maxDistanceKm: g("maxDistanceKm") ? Number(g("maxDistanceKm")) : undefined,
  });
});
