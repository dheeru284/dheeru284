import type { Gender } from "@prisma/client";
import { ACTIVE_APPOINTMENT_STATUSES } from "./appointment-states";
import type { Db } from "../db";
import { AppError } from "../errors";
import { haversineKm, type LatLng } from "../geo";
import { logger } from "../logger";
import { providers } from "../providers";
import type { RouteEstimate } from "../providers/routing";
import { addMinutes } from "../time";
import { blockWindow, isAvailable } from "./availability";
import { nurseGate, serviceGate } from "./eligibility";
import { getSetting, type MatchingSettings } from "./settings";
import { assertOperationAllowed } from "./compliance";

export type MatchRequest = {
  serviceId: string;
  location: LatLng & { city?: string; state?: string };
  startAt: Date;
  genderPreference?: Extract<Gender, "FEMALE" | "MALE">;
  languages?: string[];
  /** Patient asked for a wider search. Honoured only if admin allows; never applied silently. */
  requestExpandedLimit?: boolean;
};

export type MatchResult = {
  nurseId: string;
  displayName: string;
  gender: Gender;
  photoKey: string | null;
  serviceArea: string;
  languages: string[];
  yearsExperience: number;
  qualifications: string[];
  ratingAvg: number;
  ratingCount: number;
  completedVisits: number;
  priceInPaise: number;
  travel: { minutes: number | null; distanceKm: number | null; source: string; trafficAware: boolean; simulated: boolean; unavailable: boolean };
  score: number;
  isDemo: boolean;
};

export type MatchResponse = {
  results: MatchResult[];
  appliedLimitMinutes: number;
  limitExpanded: boolean;
  departureTimeUsed: string;
  emptyReason?: string;
  suggestions?: string[];
  excludedCounts: Record<string, number>;
};

export function scoreCandidate(
  c: { travelMinutes: number; limit: number; ratingAvg: number; ratingCount: number; yearsExperience: number; languageMatch: number; completedVisits: number },
  w: MatchingSettings["weights"],
) {
  const travel = 1 - Math.min(c.travelMinutes / c.limit, 1);
  // Bayesian-shrunk rating so a single 5★ review does not dominate.
  const rating = (c.ratingAvg * c.ratingCount + 3.5 * 5) / (c.ratingCount + 5) / 5;
  const experience = Math.min(c.yearsExperience / 15, 1);
  const reliability = Math.min(c.completedVisits / 100, 1);
  const total = w.travel + w.rating + w.experience + w.language + w.reliability || 1;
  return (w.travel * travel + w.rating * rating + w.experience * experience + w.language * c.languageMatch + w.reliability * reliability) / total;
}

/** Departure used for traffic-aware estimates: the latest the nurse could leave and still arrive with buffer. */
export function departureFor(startAt: Date, s: MatchingSettings) {
  return addMinutes(startAt, -(Math.min(s.maxTravelMinutes, 60) + s.travelBufferMinutes));
}

export async function findMatches(db: Db, req: MatchRequest, now = new Date()): Promise<MatchResponse> {
  const s = await getSetting(db, "matching");
  if (req.location.state) await assertOperationAllowed(db, "NURSING_BOOKINGS", req.location.state);

  const service = await db.nursingService.findUnique({ where: { id: req.serviceId } });
  if (!service) throw new AppError("NOT_FOUND", "Service not found");
  const sg = serviceGate(service, req.location.city);
  if (!sg.ok) throw new AppError("PRECONDITION_FAILED", "This service is not currently bookable", sg.reasons);
  if (req.startAt.getTime() < now.getTime() + s.bookingCutoffMinutes * 60_000)
    throw new AppError("VALIDATION", `Appointments must be booked at least ${s.bookingCutoffMinutes} minutes in advance`);

  let limit = s.maxTravelMinutes;
  let limitExpanded = false;
  if (req.requestExpandedLimit) {
    if (!s.allowPatientExpansion) throw new AppError("FORBIDDEN", "Expanded travel limit is not enabled");
    limit = s.expansionMaxMinutes;
    limitExpanded = true;
  }

  const { endAt, blockStart, blockEnd } = blockWindow(req.startAt, service.durationMinutes, s);
  const departAt = departureFor(req.startAt, s);
  const excluded: Record<string, number> = {};
  const bump = (k: string) => (excluded[k] = (excluded[k] ?? 0) + 1);

  // Step 1: DB-level coarse filter — approved nurses with an approved eligibility for this service.
  const nurses = await db.nurseProfile.findMany({
    where: { status: "APPROVED", isPaused: false, eligibilities: { some: { serviceId: service.id, status: "APPROVED" } }, ...(req.genderPreference ? { gender: req.genderPreference } : {}) },
    include: {
      user: { select: { status: true } },
      registrations: true,
      documents: true,
      qualifications: true,
      eligibilities: true,
      serviceAreas: true,
      availability: true,
      exceptions: { where: { endsAt: { gt: blockStart }, startsAt: { lt: blockEnd } } },
      appointments: { where: { status: { in: ACTIVE_APPOINTMENT_STATUSES }, blockEnd: { gt: addMinutes(blockStart, -1440) }, blockStart: { lt: addMinutes(blockEnd, 1440) } }, select: { blockStart: true, blockEnd: true } },
    },
  });

  const results: MatchResult[] = [];
  for (const n of nurses) {
    // Step 2: credentials.
    const gate = nurseGate(n, service, req.startAt);
    if (!gate.ok) { bump("credentials"); continue; }
    // Steps 3–4: availability and overlapping bookings (incl. travel buffer).
    const av = isAvailable(req.startAt, endAt, { blockStart, blockEnd }, n.availability, n.exceptions, n.appointments);
    if (!av.ok) { bump(av.reason ?? "unavailable"); continue; }

    const area = n.serviceAreas.find((a) => a.isPrimary) ?? n.serviceAreas[0];
    if (!area) { bump("no_service_area"); continue; }
    const origin = { lat: area.latitude, lng: area.longitude };
    if (haversineKm(origin, req.location) > s.fallbackRadiusKm) { bump("outside_radius_prefilter"); continue; }

    // Step 5: road travel-time estimate for the appointment's departure time.
    let est: RouteEstimate | null = null;
    try {
      est = await providers().routing.estimate(origin, req.location, departAt);
    } catch (err) {
      logger.warn("matching.routing_error", { err: String(err) });
    }
    const nurseLimit = Math.min(limit, area.maxTravelMinutes ?? limit);
    if (!est) {
      if (s.routingUnavailablePolicy === "EXCLUDE") { bump("travel_estimate_unavailable"); continue; }
    } else {
      // Step 6: travel-time threshold (and optional road-distance cap).
      if (est.minutes > nurseLimit) { bump("beyond_travel_limit"); continue; }
      if (s.maxRoadDistanceKm != null && est.distanceKm > s.maxRoadDistanceKm) { bump("beyond_distance_limit"); continue; }
    }

    const wanted = req.languages ?? [];
    const languageMatch = wanted.length ? wanted.filter((l) => n.languages.includes(l)).length / wanted.length : 0.5;
    const elig = n.eligibilities.find((e) => e.serviceId === service.id)!;
    // Step 7: rank. Unavailable estimates rank as if at the limit and require manual confirmation.
    const score = scoreCandidate(
      { travelMinutes: est?.minutes ?? nurseLimit, limit: nurseLimit, ratingAvg: n.ratingAvg, ratingCount: n.ratingCount, yearsExperience: n.yearsExperience, languageMatch, completedVisits: n.completedVisits },
      s.weights,
    );
    results.push({
      nurseId: n.id,
      displayName: n.displayName,
      gender: n.gender,
      photoKey: n.photoKey,
      serviceArea: area.label, // never the dispatch coordinates or home address
      languages: n.languages,
      yearsExperience: n.yearsExperience,
      qualifications: n.qualifications.filter((q) => q.verificationStatus === "VERIFIED").map((q) => q.code),
      ratingAvg: n.ratingAvg,
      ratingCount: n.ratingCount,
      completedVisits: n.completedVisits,
      priceInPaise: (elig.priceInPaise ?? service.basePriceInPaise) + service.travelChargeInPaise,
      travel: est
        ? { minutes: est.minutes, distanceKm: est.distanceKm, source: est.provider, trafficAware: est.trafficAware, simulated: est.simulated, unavailable: false }
        : { minutes: null, distanceKm: null, source: "UNAVAILABLE", trafficAware: false, simulated: false, unavailable: true },
      score: Math.round(score * 1000) / 1000,
      isDemo: n.isDemo,
    });
  }

  results.sort((a, b) => b.score - a.score);
  const top = results.slice(0, s.maxResults);
  const res: MatchResponse = { results: top, appliedLimitMinutes: limit, limitExpanded, departureTimeUsed: departAt.toISOString(), excludedCounts: excluded };
  if (!top.length) {
    res.emptyReason = `No eligible nurse was found within the ${limit}-minute travel-time limit for this time.`;
    res.suggestions = ["Try a different time on the same day", "Try a different date"];
    if (s.allowPatientExpansion && !limitExpanded) res.suggestions.push(`Request an expanded search up to ${s.expansionMaxMinutes} minutes`);
  }
  return res;
}
