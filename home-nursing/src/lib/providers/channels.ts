import { logger } from "../logger";

export interface EmailProvider {
  readonly name: string;
  send(to: string, subject: string, text: string): Promise<{ ok: boolean; error?: string }>;
}
export interface WhatsAppProvider {
  readonly name: string;
  send(toE164: string, templateName: string, params: string[], language?: string): Promise<{ ok: boolean; error?: string }>;
}

/** SMTP (any provider: SES SMTP, SendGrid SMTP, Zoho, etc.). */
export class SmtpEmailProvider implements EmailProvider {
  readonly name = "smtp";
  constructor(private cfg: { url: string; from: string }) {}
  async send(to: string, subject: string, text: string) {
    try {
      const nodemailer = await import("nodemailer");
      await nodemailer.createTransport(this.cfg.url).sendMail({ from: this.cfg.from, to, subject, text });
      return { ok: true };
    } catch (e) {
      return { ok: false, error: e instanceof Error ? e.message : String(e) };
    }
  }
}

/** Meta WhatsApp Cloud API — template messages only (required for business-initiated messages). */
export class WhatsAppCloudProvider implements WhatsAppProvider {
  readonly name = "whatsapp-cloud";
  constructor(private token: string, private phoneNumberId: string, private fetchImpl: typeof fetch = fetch) {}
  async send(to: string, templateName: string, params: string[], language = "en") {
    const res = await this.fetchImpl(`https://graph.facebook.com/v21.0/${this.phoneNumberId}/messages`, {
      method: "POST",
      headers: { authorization: `Bearer ${this.token}`, "content-type": "application/json" },
      body: JSON.stringify({ messaging_product: "whatsapp", to: to.replace(/^\+/, ""), type: "template", template: { name: templateName, language: { code: language }, components: [{ type: "body", parameters: params.map((text) => ({ type: "text", text })) }] } }),
    }).catch(() => null);
    if (!res?.ok) return { ok: false, error: `whatsapp: ${res?.status ?? "network"}` };
    return { ok: true };
  }
}

/** DEVELOPMENT ONLY: records messages in memory. */
export class MockEmailProvider implements EmailProvider {
  readonly name = "mock";
  readonly outbox: { to: string; subject: string }[] = [];
  async send(to: string, subject: string) {
    this.outbox.push({ to, subject });
    logger.info("email.mock.sent", { subject });
    return { ok: true };
  }
}
export class MockWhatsAppProvider implements WhatsAppProvider {
  readonly name = "mock";
  readonly outbox: { to: string; templateName: string }[] = [];
  async send(to: string, templateName: string) {
    this.outbox.push({ to, templateName });
    return { ok: true };
  }
}
