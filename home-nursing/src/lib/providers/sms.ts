import { logger } from "../logger";

export interface SmsProvider {
  readonly name: string;
  send(toE164: string, body: string): Promise<{ ok: boolean; providerId?: string; error?: string }>;
}

/** DEVELOPMENT ONLY. Records messages in memory; never prints message bodies (may contain OTPs). */
export class MockSmsProvider implements SmsProvider {
  readonly name = "mock";
  readonly outbox: { to: string; body: string; at: Date }[] = [];
  async send(to: string, body: string) {
    this.outbox.push({ to, body, at: new Date() });
    logger.info("sms.mock.sent", { to: to.slice(0, -4) + "****" });
    return { ok: true, providerId: `mock_${this.outbox.length}` };
  }
}
