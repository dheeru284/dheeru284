import { Prisma } from "@prisma/client";
import { prisma, type Db } from "../db";
import { AppError } from "../errors";
import { haversineKm } from "../geo";
import { providers } from "../providers";
import type { Principal } from "../auth/session";
import { nightsBetween } from "../time";
import { audit } from "./audit";
import { newReference } from "./appointments";
import { assertOperationAllowed } from "./compliance";
import { notify } from "./notifications";
import { getSetting } from "./settings";

const ACTIVE_STAY = ["REQUESTED", "CONFIRMED", "CHECKED_IN"] as const;

export function quoteStay(rate: { nightlyInPaise: number; monthlyInPaise: number | null; extendedStayDiscountPct: number; depositInPaise: number }, nights: number) {
  let total: number;
  if (nights >= 30 && rate.monthlyInPaise) {
    const months = Math.floor(nights / 30);
    total = months * rate.monthlyInPaise + (nights - months * 30) * rate.nightlyInPaise;
  } else {
    total = nights * rate.nightlyInPaise;
    if (nights >= 14) total = Math.round(total * (1 - rate.extendedStayDiscountPct / 100));
  }
  return { nights, totalInPaise: total, depositInPaise: rate.depositInPaise };
}

const parseDate = (d: string) => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(d)) throw new AppError("VALIDATION", "Dates must be YYYY-MM-DD");
  return new Date(`${d}T00:00:00Z`);
};

export type StaySearch = { hospitalId: string; checkIn: string; checkOut: string; guests: number; maxNightlyInPaise?: number; amenities?: string[]; accessibility?: string[]; propertyType?: string; maxDistanceKm?: number };

export async function searchStays(db: Db, q: StaySearch) {
  const checkIn = parseDate(q.checkIn), checkOut = parseDate(q.checkOut);
  const nights = nightsBetween(checkIn, checkOut);
  if (nights < 1 || nights > 365) throw new AppError("VALIDATION", "Stay must be between 1 and 365 nights");
  const hospital = await db.hospital.findFirst({ where: { id: q.hospitalId, isActive: true } });
  if (!hospital) throw new AppError("NOT_FOUND", "Hospital not found");
  const props = await db.accommodationProperty.findMany({
    where: {
      city: hospital.city, isActive: true, verificationStatus: "VERIFIED", maxGuests: { gte: q.guests }, minStayNights: { lte: nights },
      ...(q.propertyType ? { propertyType: q.propertyType } : {}),
      ...(q.accessibility?.length ? { accessibility: { hasEvery: q.accessibility } } : {}),
      ...(q.amenities?.length ? { AND: q.amenities.map((a) => ({ amenities: { some: { amenity: a } } })) } : {}),
      blackouts: { none: { startDate: { lt: checkOut }, endDate: { gt: checkIn } } },
    },
    include: {
      images: true, amenities: true,
      rates: { where: { validFrom: { lte: checkIn }, OR: [{ validTo: null }, { validTo: { gte: checkOut } }] }, orderBy: { validFrom: "desc" }, take: 1 },
      units: { include: { bookings: { where: { status: { in: [...ACTIVE_STAY] }, checkIn: { lt: checkOut }, checkOut: { gt: checkIn } }, select: { id: true } } } },
    },
  });
  const out = [];
  for (const p of props) {
    const rate = p.rates[0];
    const freeUnits = p.units.filter((u) => u.bookings.length === 0).length;
    if (!rate || freeUnits === 0) continue;
    const quote = quoteStay(rate, nights);
    if (q.maxNightlyInPaise && quote.totalInPaise / nights > q.maxNightlyInPaise) continue;
    const straightKm = haversineKm({ lat: hospital.latitude, lng: hospital.longitude }, { lat: p.latitude, lng: p.longitude });
    if (q.maxDistanceKm && straightKm > q.maxDistanceKm) continue;
    let travel: { minutes: number; distanceKm: number; source: string; simulated: boolean } | null = null;
    try {
      const est = await providers().routing.estimate({ lat: p.latitude, lng: p.longitude }, { lat: hospital.latitude, lng: hospital.longitude }, new Date(`${q.checkIn}T03:30:00Z`));
      if (est) travel = { minutes: est.minutes, distanceKm: est.distanceKm, source: est.provider, simulated: est.simulated };
    } catch { /* labelled as unavailable below */ }
    out.push({
      id: p.id, name: p.name, propertyType: p.propertyType, city: p.city, bedrooms: p.bedrooms, bathrooms: p.bathrooms, maxGuests: p.maxGuests,
      accessibility: p.accessibility, amenities: p.amenities.map((a) => a.amenity), image: p.images[0] ?? null, isDemo: p.isDemo,
      straightLineKm: Math.round(straightKm * 10) / 10, travelToHospital: travel, freeUnits, quote, cancellationPolicy: p.cancellationPolicy,
    });
  }
  out.sort((a, b) => a.straightLineKm - b.straightLineKm);
  return { hospital: { id: hospital.id, name: hospital.name, city: hospital.city }, nights, results: out };
}

const isStayOverlap = (e: unknown) => e instanceof Error && /stay_no_unit_overlap|exclusion constraint|23P01|40P01|deadlock detected/.test(e.message + JSON.stringify((e as Prisma.PrismaClientKnownRequestError).meta ?? {}));

/** Picks a free unit and inserts the booking; the DB exclusion constraint makes concurrent requests safe. */
export async function requestStay(p: Principal, input: { propertyId: string; checkIn: string; checkOut: string; guests: number; hospitalId?: string; guestNote?: string; extendedFromId?: string }, db: typeof prisma = prisma) {
  const checkIn = parseDate(input.checkIn), checkOut = parseDate(input.checkOut);
  const nights = nightsBetween(checkIn, checkOut);
  if (nights < 1) throw new AppError("VALIDATION", "Check-out must be after check-in");
  const prop = await db.accommodationProperty.findFirst({
    where: { id: input.propertyId, isActive: true, verificationStatus: "VERIFIED" },
    include: { partner: true, units: true, rates: { where: { validFrom: { lte: checkIn }, OR: [{ validTo: null }, { validTo: { gte: checkOut } }] }, orderBy: { validFrom: "desc" }, take: 1 }, blackouts: { where: { startDate: { lt: checkOut }, endDate: { gt: checkIn } } } },
  });
  if (!prop) throw new AppError("NOT_FOUND", "Property not found");
  await assertOperationAllowed(db, "ACCOMMODATION_BOOKINGS", prop.state);
  if (input.guests > prop.maxGuests) throw new AppError("VALIDATION", "Too many guests for this property");
  if (nights < prop.minStayNights) throw new AppError("VALIDATION", `Minimum stay is ${prop.minStayNights} nights`);
  if (prop.blackouts.length) throw new AppError("CONFLICT", "Property is unavailable for these dates");
  const rate = prop.rates[0];
  if (!rate) throw new AppError("PRECONDITION_FAILED", "No rate configured for these dates");
  const quote = quoteStay(rate, nights);
  const c = await getSetting(db, "commerce");

  for (const unit of prop.units) {
    try {
      const b = await db.accommodationBooking.create({
        data: {
          reference: newReference("ST"), userId: p.userId, unitId: unit.id, hospitalId: input.hospitalId, checkIn, checkOut, guests: input.guests,
          totalInPaise: quote.totalInPaise, depositInPaise: quote.depositInPaise, commissionInPaise: Math.round((quote.totalInPaise * c.accommodationCommissionPct) / 100),
          guestNote: input.guestNote, extendedFromId: input.extendedFromId,
        },
      });
      await notify(db, prop.partner.userId, "stay.requested", { ref: b.reference, dates: `${input.checkIn} → ${input.checkOut}` });
      return b;
    } catch (e) {
      if (isStayOverlap(e)) continue; // unit taken, try next
      throw e;
    }
  }
  throw new AppError("CONFLICT", "No units are available for these dates");
}

/** Extension = a new booking for the following nights on the same unit, subject to availability. */
export async function extendStay(p: Principal, bookingId: string, newCheckOut: string, db: typeof prisma = prisma) {
  const b = await db.accommodationBooking.findFirst({ where: { id: bookingId, userId: p.userId, status: { in: ["CONFIRMED", "CHECKED_IN"] } }, include: { unit: { include: { property: { include: { partner: true, rates: { orderBy: { validFrom: "desc" }, take: 1 } } } } } } });
  if (!b) throw new AppError("NOT_FOUND", "Booking not found");
  const end = parseDate(newCheckOut);
  const nights = nightsBetween(b.checkOut, end);
  if (nights < 1) throw new AppError("VALIDATION", "New check-out must be after the current one");
  const rate = b.unit.property.rates[0]!;
  const quote = quoteStay(rate, nights);
  try {
    return await db.accommodationBooking.create({
      data: { reference: newReference("ST"), userId: p.userId, unitId: b.unitId, hospitalId: b.hospitalId, checkIn: b.checkOut, checkOut: end, guests: b.guests, totalInPaise: quote.totalInPaise, depositInPaise: 0, commissionInPaise: Math.round((quote.totalInPaise * (await getSetting(db, "commerce")).accommodationCommissionPct) / 100), extendedFromId: b.id },
    });
  } catch (e) {
    if (isStayOverlap(e)) throw new AppError("CONFLICT", "The unit is not available for the extension dates");
    throw e;
  }
}

async function partnerIdFor(db: Db, p: Principal) {
  const partner = await db.accommodationPartner.findUnique({ where: { userId: p.userId } });
  if (!partner) throw new AppError("FORBIDDEN", "Partner profile required");
  return partner.id;
}

/** Partner sees only bookings on their own properties and only the guest's name/phone — never clinical data. */
export async function partnerBookings(p: Principal, db: Db = prisma) {
  const partnerId = await partnerIdFor(db, p);
  const rows = await db.accommodationBooking.findMany({ where: { unit: { property: { partnerId } } }, include: { unit: { include: { property: { select: { name: true } } } }, user: { select: { fullName: true, phone: true } } }, orderBy: { checkIn: "asc" } });
  return rows.map((r) => ({ id: r.id, reference: r.reference, property: r.unit.property.name, unit: r.unit.label, checkIn: r.checkIn, checkOut: r.checkOut, guests: r.guests, status: r.status, totalInPaise: r.totalInPaise, guest: { name: r.user.fullName, phone: r.user.phone }, guestNote: r.guestNote }));
}

export async function partnerRespond(p: Principal, bookingId: string, decision: "CONFIRMED" | "DECLINED", db: Db = prisma) {
  const partnerId = await partnerIdFor(db, p);
  const r = await db.accommodationBooking.updateMany({ where: { id: bookingId, status: "REQUESTED", unit: { property: { partnerId } } }, data: { status: decision } });
  if (r.count !== 1) throw new AppError("NOT_FOUND", "Pending booking not found");
  const b = await db.accommodationBooking.findUniqueOrThrow({ where: { id: bookingId } });
  await notify(db, b.userId, "stay.status", { ref: b.reference, status: decision.toLowerCase() });
  await audit(db, { actorUserId: p.userId, action: `stay.${decision.toLowerCase()}`, entityType: "AccommodationBooking", entityId: bookingId });
  return b;
}

export async function cancelStay(p: Principal, bookingId: string, db: Db = prisma) {
  const r = await db.accommodationBooking.updateMany({ where: { id: bookingId, userId: p.userId, status: { in: ["REQUESTED", "CONFIRMED"] } }, data: { status: "CANCELLED" } });
  if (r.count !== 1) throw new AppError("NOT_FOUND", "Cancellable booking not found");
  return db.accommodationBooking.findUniqueOrThrow({ where: { id: bookingId } });
}
