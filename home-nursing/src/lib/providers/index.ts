import { env } from "../env";
import { prisma } from "../db";
import { CachedRoutingProvider, GoogleRoutesProvider, SimulatedRoutingProvider, type RouteEstimate, type RoutingProvider } from "./routing";
import { MockSmsProvider, type SmsProvider } from "./sms";
import { MockPaymentProvider, RazorpayProvider, type PaymentProvider } from "./payments";
import { MockStorageProvider, type StorageProvider } from "./storage";

// Provider registry. Core domain code depends only on the interfaces; tests swap implementations via setProviders().
type Registry = { routing: RoutingProvider; sms: SmsProvider; payments: PaymentProvider; storage: StorageProvider };
let registry: Registry | undefined;

const dbRouteCache = {
  async get(key: string): Promise<RouteEstimate | null> {
    const row = await prisma.routeCacheEntry.findUnique({ where: { key } });
    if (!row || row.expiresAt < new Date()) return null;
    return { minutes: row.minutes, distanceKm: row.distanceKm, provider: row.provider, trafficAware: row.trafficAware, simulated: row.provider === "simulated" };
  },
  async set(key: string, v: RouteEstimate, ttlSec: number) {
    const data = { minutes: v.minutes, distanceKm: v.distanceKm, provider: v.provider, trafficAware: v.trafficAware, expiresAt: new Date(Date.now() + ttlSec * 1000) };
    await prisma.routeCacheEntry.upsert({ where: { key }, create: { key, ...data }, update: data });
  },
};

function build(): Registry {
  const e = env();
  const baseRouting = e.ROUTING_PROVIDER === "google" ? new GoogleRoutesProvider(e.GOOGLE_MAPS_API_KEY!) : new SimulatedRoutingProvider();
  // SMS: only the mock is implemented in-repo; a production adapter (e.g. MSG91/DLT-registered) plugs in here.
  const sms: SmsProvider = new MockSmsProvider();
  const payments: PaymentProvider =
    e.PAYMENT_PROVIDER === "razorpay" ? new RazorpayProvider(e.RAZORPAY_KEY_ID!, e.RAZORPAY_KEY_SECRET!, e.RAZORPAY_WEBHOOK_SECRET!) : new MockPaymentProvider();
  return { routing: new CachedRoutingProvider(baseRouting, dbRouteCache, 15 * 60), sms, payments, storage: new MockStorageProvider() };
}

export function providers(): Registry {
  return (registry ??= build());
}

export function setProviders(p: Partial<Registry>) {
  registry = { ...providers(), ...p };
}
