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

/**
 * MSG91 (India, DLT-compliant). Each message must map to a DLT-approved template; `templateFor` resolves it.
 * The message body is sent as template variables, never free text.
 */
export class Msg91SmsProvider implements SmsProvider {
  readonly name = "msg91";
  constructor(private authKey: string, private defaultTemplateId: string, private otpTemplateId: string, private fetchImpl: typeof fetch = fetch) {}
  async send(to: string, body: string) {
    const isOtp = /verification code/i.test(body);
    const res = await this.fetchImpl("https://control.msg91.com/api/v5/flow", {
      method: "POST",
      headers: { authkey: this.authKey, "content-type": "application/json", accept: "application/json" },
      body: JSON.stringify({ template_id: isOtp ? this.otpTemplateId : this.defaultTemplateId, short_url: "0", recipients: [{ mobiles: to.replace(/^\+/, ""), var1: isOtp ? body.slice(0, 6) : body }] }),
      signal: AbortSignal.timeout(8000),
    }).catch((e: unknown) => ({ ok: false, status: 0, json: async () => ({ message: String(e) }) }) as unknown as Response);
    const json = (await res.json().catch(() => ({}))) as { type?: string; message?: string };
    if (!res.ok || json.type === "error") return { ok: false, error: `msg91: ${res.status} ${json.message ?? ""}`.trim() };
    return { ok: true, providerId: json.message };
  }
}
