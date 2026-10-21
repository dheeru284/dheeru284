import { z } from "zod";
import type { Db } from "../db";
import { AppError } from "../errors";
import { audit } from "./audit";

export const matchingSettingsSchema = z.object({
  maxTravelMinutes: z.number().int().min(10).max(480),
  maxRoadDistanceKm: z.number().positive().nullable(),
  fallbackRadiusKm: z.number().positive(), // coarse pre-filter before routing; never a substitute for travel time
  allowPatientExpansion: z.boolean(), // may patients request an expanded limit?
  expansionMaxMinutes: z.number().int().min(10).max(480),
  travelBufferMinutes: z.number().int().min(0).max(120),
  appointmentBufferMinutes: z.number().int().min(0).max(120),
  routingUnavailablePolicy: z.enum(["EXCLUDE", "INCLUDE_FLAGGED_MANUAL_CONFIRM"]),
  routeCacheSeconds: z.number().int().min(0).max(86400),
  bookingCutoffMinutes: z.number().int().min(0).max(7 * 1440),
  maxResults: z.number().int().min(1).max(50),
  weights: z.object({
    travel: z.number().min(0),
    rating: z.number().min(0),
    experience: z.number().min(0),
    language: z.number().min(0),
    reliability: z.number().min(0),
  }),
});
export type MatchingSettings = z.infer<typeof matchingSettingsSchema>;

export const DEFAULT_MATCHING: MatchingSettings = {
  maxTravelMinutes: 120,
  maxRoadDistanceKm: null,
  fallbackRadiusKm: 150,
  allowPatientExpansion: false,
  expansionMaxMinutes: 150,
  travelBufferMinutes: 15,
  appointmentBufferMinutes: 10,
  routingUnavailablePolicy: "EXCLUDE",
  routeCacheSeconds: 900,
  bookingCutoffMinutes: 120,
  maxResults: 10,
  weights: { travel: 0.4, rating: 0.25, experience: 0.15, language: 0.1, reliability: 0.1 },
};

export const commerceSettingsSchema = z.object({
  nursingCommissionPct: z.number().min(0).max(50),
  nursingFixedFeeInPaise: z.number().int().min(0),
  accommodationCommissionPct: z.number().min(0).max(50),
  freeCancellationHours: z.number().int().min(0),
  lateCancellationFeePct: z.number().min(0).max(100),
});
export type CommerceSettings = z.infer<typeof commerceSettingsSchema>;
export const DEFAULT_COMMERCE: CommerceSettings = {
  nursingCommissionPct: 15,
  nursingFixedFeeInPaise: 0,
  accommodationCommissionPct: 10,
  freeCancellationHours: 4,
  lateCancellationFeePct: 50,
};

const REGISTRY = {
  matching: { schema: matchingSettingsSchema, def: DEFAULT_MATCHING },
  commerce: { schema: commerceSettingsSchema, def: DEFAULT_COMMERCE },
} as const;
type Key = keyof typeof REGISTRY;

export async function getSetting<K extends Key>(db: Db, key: K): Promise<z.infer<(typeof REGISTRY)[K]["schema"]>> {
  const row = await db.platformSetting.findUnique({ where: { key } });
  const { schema, def } = REGISTRY[key];
  if (!row) return def as never;
  return schema.parse({ ...def, ...(row.value as object) }) as never;
}

/** Runtime-configurable; no redeploy needed. Every change is audited with before/after values. */
export async function updateSetting<K extends Key>(db: Db, key: K, patch: unknown, actorUserId: string) {
  const before = await getSetting(db, key);
  const parsed = REGISTRY[key].schema.safeParse({ ...before, ...(patch as object) });
  if (!parsed.success) throw new AppError("VALIDATION", "Invalid settings", parsed.error.flatten());
  await db.platformSetting.upsert({ where: { key }, create: { key, value: parsed.data, updatedBy: actorUserId }, update: { value: parsed.data, updatedBy: actorUserId } });
  await audit(db, { actorUserId, action: "settings.update", entityType: "PlatformSetting", entityId: key, metadata: { before, after: parsed.data } as never });
  if (key === "matching") await db.routeCacheEntry.deleteMany({}); // cache semantics may have changed
  return parsed.data;
}

export async function isFeatureEnabled(db: Db, key: string, city?: string) {
  const f = await db.featureFlag.findUnique({ where: { key } });
  if (!f?.enabled) return false;
  return !city || f.rolloutCities.length === 0 || f.rolloutCities.includes(city);
}
