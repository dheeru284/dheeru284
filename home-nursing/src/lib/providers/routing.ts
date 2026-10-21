import { createHash } from "node:crypto";
import { haversineKm, type LatLng } from "../geo";
import { logger } from "../logger";

export type RouteEstimate = {
  minutes: number;
  distanceKm: number;
  provider: string;
  /** True only when the provider used traffic for the requested departure time. */
  trafficAware: boolean;
  /** True for the development simulator. UI must label these as simulated. */
  simulated: boolean;
};

export interface RoutingProvider {
  readonly name: string;
  /** Returns null when the provider cannot produce an estimate. Never fabricate a value. */
  estimate(origin: LatLng, destination: LatLng, departAt: Date): Promise<RouteEstimate | null>;
}

/**
 * DEVELOPMENT ONLY. Approximates road travel with a detour factor and time-of-day speed profile.
 * It is NOT a road estimate; results carry simulated=true and production config refuses this provider.
 */
export class SimulatedRoutingProvider implements RoutingProvider {
  readonly name = "simulated";
  constructor(private opts: { failWith?: "null" | "throw" } = {}) {}
  async estimate(o: LatLng, d: LatLng, departAt: Date): Promise<RouteEstimate | null> {
    if (this.opts.failWith === "throw") throw new Error("simulated outage");
    if (this.opts.failWith === "null") return null;
    const roadKm = haversineKm(o, d) * 1.35;
    const hourIst = (departAt.getUTCHours() + 5.5) % 24;
    const peak = (hourIst >= 8 && hourIst < 11) || (hourIst >= 17 && hourIst < 21);
    const kmh = peak ? 18 : 28;
    return { minutes: Math.ceil((roadKm / kmh) * 60) + 5, distanceKm: Math.round(roadKm * 10) / 10, provider: this.name, trafficAware: false, simulated: true };
  }
}

/** Google Maps Platform Routes API (computeRoutes) with traffic-aware routing for the departure time. */
export class GoogleRoutesProvider implements RoutingProvider {
  readonly name = "google-routes";
  constructor(private apiKey: string, private fetchImpl: typeof fetch = fetch) {}
  async estimate(o: LatLng, d: LatLng, departAt: Date): Promise<RouteEstimate | null> {
    const future = departAt.getTime() > Date.now() + 60_000;
    const body = {
      origin: { location: { latLng: { latitude: o.lat, longitude: o.lng } } },
      destination: { location: { latLng: { latitude: d.lat, longitude: d.lng } } },
      travelMode: "DRIVE",
      routingPreference: future ? "TRAFFIC_AWARE_OPTIMAL" : "TRAFFIC_AWARE",
      ...(future ? { departureTime: departAt.toISOString() } : {}),
    };
    const res = await this.fetchImpl("https://routes.googleapis.com/directions/v2:computeRoutes", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Goog-Api-Key": this.apiKey, "X-Goog-FieldMask": "routes.duration,routes.distanceMeters" },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(5000),
    });
    if (!res.ok) {
      logger.warn("routing.google.http_error", { status: res.status });
      return null;
    }
    const json = (await res.json()) as { routes?: { duration?: string; distanceMeters?: number }[] };
    const r = json.routes?.[0];
    if (!r?.duration || r.distanceMeters == null) return null;
    return { minutes: Math.ceil(parseInt(r.duration, 10) / 60), distanceKm: r.distanceMeters / 1000, provider: this.name, trafficAware: true, simulated: false };
  }
}

/** Caches estimates per origin/destination/15-minute departure bucket. */
export class CachedRoutingProvider implements RoutingProvider {
  constructor(
    private inner: RoutingProvider,
    private store: { get(k: string): Promise<RouteEstimate | null>; set(k: string, v: RouteEstimate, ttlSec: number): Promise<void> },
    private ttlSec: number,
  ) {}
  get name() {
    return this.inner.name;
  }
  static key(provider: string, o: LatLng, d: LatLng, departAt: Date) {
    const bucket = Math.floor(departAt.getTime() / (15 * 60_000));
    const r = (n: number) => n.toFixed(5); // changed coordinates → different key (implicit invalidation)
    return createHash("sha256").update(`${provider}|${r(o.lat)},${r(o.lng)}|${r(d.lat)},${r(d.lng)}|${bucket}`).digest("hex");
  }
  async estimate(o: LatLng, d: LatLng, departAt: Date) {
    const k = CachedRoutingProvider.key(this.inner.name, o, d, departAt);
    const hit = await this.store.get(k);
    if (hit) return hit;
    const v = await this.inner.estimate(o, d, departAt);
    if (v) await this.store.set(k, v, this.ttlSec); // failures are never cached
    return v;
  }
}
