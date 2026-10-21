import { z } from "zod";

const schema = z.object({
  NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
  DATABASE_URL: z.string().min(1),
  APP_URL: z.string().url().default("http://localhost:3000"),
  OTP_SECRET: z.string().min(16).default("dev-only-otp-secret-change-me"),
  SESSION_TTL_HOURS: z.coerce.number().int().positive().default(24 * 7),
  SMS_PROVIDER: z.enum(["mock", "msg91"]).default("mock"),
  MSG91_AUTH_KEY: z.string().optional(),
  MSG91_TEMPLATE_ID: z.string().optional(),
  MSG91_OTP_TEMPLATE_ID: z.string().optional(),
  EMAIL_PROVIDER: z.enum(["none", "mock", "smtp"]).default("mock"),
  SMTP_URL: z.string().optional(),
  EMAIL_FROM: z.string().optional(),
  WHATSAPP_PROVIDER: z.enum(["none", "mock", "cloud"]).default("none"),
  WHATSAPP_TOKEN: z.string().optional(),
  WHATSAPP_PHONE_NUMBER_ID: z.string().optional(),
  GEOCODING_PROVIDER: z.enum(["dev", "google"]).default("dev"),
  ROUTING_PROVIDER: z.enum(["simulated", "google"]).default("simulated"),
  GOOGLE_MAPS_API_KEY: z.string().optional(),
  PAYMENT_PROVIDER: z.enum(["mock", "razorpay"]).default("mock"),
  RAZORPAY_KEY_ID: z.string().optional(),
  RAZORPAY_KEY_SECRET: z.string().optional(),
  RAZORPAY_WEBHOOK_SECRET: z.string().optional(),
  STORAGE_PROVIDER: z.enum(["mock", "s3"]).default("mock"),
  S3_BUCKET: z.string().optional(),
  S3_REGION: z.string().default("ap-south-1"),
  S3_ENDPOINT: z.string().optional(),
  S3_ACCESS_KEY_ID: z.string().optional(),
  S3_SECRET_ACCESS_KEY: z.string().optional(),
  ERROR_WEBHOOK_URL: z.string().url().optional(),
  DEV_EXPOSE_OTP: z.enum(["true", "false"]).default("false"),
});

export type Env = z.infer<typeof schema>;

let cached: Env | undefined;

export function env(): Env {
  if (cached) return cached;
  const parsed = schema.parse(process.env);
  assertProductionSafe(parsed);
  cached = parsed;
  return parsed;
}

/** Mock adapters are development-only. Production must name real providers explicitly. */
export function assertProductionSafe(e: Env): void {
  if (e.NODE_ENV !== "production") return;
  const problems: string[] = [];
  if (e.OTP_SECRET.startsWith("dev-only")) problems.push("OTP_SECRET must be set");
  if (e.SMS_PROVIDER === "mock") problems.push("SMS_PROVIDER=mock is not allowed in production");
  if (e.ROUTING_PROVIDER === "simulated") problems.push("ROUTING_PROVIDER=simulated is not allowed in production");
  if (e.PAYMENT_PROVIDER === "mock") problems.push("PAYMENT_PROVIDER=mock is not allowed in production");
  if (e.STORAGE_PROVIDER === "mock") problems.push("STORAGE_PROVIDER=mock is not allowed in production");
  if (e.DEV_EXPOSE_OTP === "true") problems.push("DEV_EXPOSE_OTP must be false in production");
  if (e.SMS_PROVIDER === "msg91" && !(e.MSG91_AUTH_KEY && e.MSG91_TEMPLATE_ID && e.MSG91_OTP_TEMPLATE_ID)) problems.push("MSG91 keys/template IDs missing");
  if (e.STORAGE_PROVIDER === "s3" && !e.S3_BUCKET) problems.push("S3_BUCKET missing");
  if (e.EMAIL_PROVIDER === "mock") problems.push("EMAIL_PROVIDER=mock is not allowed in production (use smtp or none)");
  if (e.EMAIL_PROVIDER === "smtp" && !(e.SMTP_URL && e.EMAIL_FROM)) problems.push("SMTP_URL/EMAIL_FROM missing");
  if (e.WHATSAPP_PROVIDER === "mock") problems.push("WHATSAPP_PROVIDER=mock is not allowed in production");
  if (e.WHATSAPP_PROVIDER === "cloud" && !(e.WHATSAPP_TOKEN && e.WHATSAPP_PHONE_NUMBER_ID)) problems.push("WhatsApp credentials missing");
  if (e.GEOCODING_PROVIDER === "dev") problems.push("GEOCODING_PROVIDER=dev is not allowed in production");
  if ((e.GEOCODING_PROVIDER === "google" || e.ROUTING_PROVIDER === "google") && !e.GOOGLE_MAPS_API_KEY) problems.push("GOOGLE_MAPS_API_KEY missing");
  if (e.PAYMENT_PROVIDER === "razorpay" && !(e.RAZORPAY_KEY_ID && e.RAZORPAY_KEY_SECRET && e.RAZORPAY_WEBHOOK_SECRET))
    problems.push("Razorpay keys missing");
  if (problems.length) throw new Error(`Unsafe production configuration:\n- ${problems.join("\n- ")}`);
}
