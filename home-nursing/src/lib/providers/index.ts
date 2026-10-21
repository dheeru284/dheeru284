import { env } from "../env";
import { prisma } from "../db";
import { CachedRoutingProvider, GoogleRoutesProvider, SimulatedRoutingProvider, type RouteEstimate, type RoutingProvider } from "./routing";
import { MockSmsProvider, Msg91SmsProvider, type SmsProvider } from "./sms";
import { MockPaymentProvider, RazorpayProvider, type PaymentProvider } from "./payments";
import { MockStorageProvider, S3StorageProvider, type StorageProvider } from "./storage";
import { MockEmailProvider, MockWhatsAppProvider, SmtpEmailProvider, WhatsAppCloudProvider, type EmailProvider, type WhatsAppProvider } from "./channels";
import { DevGazetteerGeocoder, GoogleGeocodingProvider, type GeocodingProvider } from "./geocoding";

// Provider registry. Domain code depends only on interfaces; tests swap implementations via setProviders().
type Registry = {
  routing: RoutingProvider; sms: SmsProvider; payments: PaymentProvider; storage: StorageProvider;
  email: EmailProvider | null; whatsapp: WhatsAppProvider | null; geocoding: GeocodingProvider;
};
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
  return {
    routing: new CachedRoutingProvider(baseRouting, dbRouteCache, 15 * 60),
    sms: e.SMS_PROVIDER === "msg91" ? new Msg91SmsProvider(e.MSG91_AUTH_KEY!, e.MSG91_TEMPLATE_ID!, e.MSG91_OTP_TEMPLATE_ID!) : new MockSmsProvider(),
    payments: e.PAYMENT_PROVIDER === "razorpay" ? new RazorpayProvider(e.RAZORPAY_KEY_ID!, e.RAZORPAY_KEY_SECRET!, e.RAZORPAY_WEBHOOK_SECRET!) : new MockPaymentProvider(),
    storage: e.STORAGE_PROVIDER === "s3" ? new S3StorageProvider({ bucket: e.S3_BUCKET!, region: e.S3_REGION, endpoint: e.S3_ENDPOINT, accessKeyId: e.S3_ACCESS_KEY_ID, secretAccessKey: e.S3_SECRET_ACCESS_KEY }) : new MockStorageProvider(),
    email: e.EMAIL_PROVIDER === "smtp" ? new SmtpEmailProvider({ url: e.SMTP_URL!, from: e.EMAIL_FROM! }) : e.EMAIL_PROVIDER === "mock" ? new MockEmailProvider() : null,
    whatsapp: e.WHATSAPP_PROVIDER === "cloud" ? new WhatsAppCloudProvider(e.WHATSAPP_TOKEN!, e.WHATSAPP_PHONE_NUMBER_ID!) : e.WHATSAPP_PROVIDER === "mock" ? new MockWhatsAppProvider() : null,
    geocoding: e.GEOCODING_PROVIDER === "google" ? new GoogleGeocodingProvider(e.GOOGLE_MAPS_API_KEY!) : new DevGazetteerGeocoder(),
  };
}

export function providers(): Registry {
  return (registry ??= build());
}

export function setProviders(p: Partial<Registry>) {
  registry = { ...providers(), ...p };
}
