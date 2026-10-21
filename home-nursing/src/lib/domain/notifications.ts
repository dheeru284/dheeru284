import type { Prisma } from "@prisma/client";
import type { Db } from "../db";
import { logger } from "../logger";
import { providers } from "../providers";
import { isFeatureEnabled } from "./settings";

export type Channel = "IN_APP" | "SMS" | "EMAIL" | "WHATSAPP";

/** Template keys → default English bodies. Bodies must never include diagnoses, procedures or medical details. */
export const DEFAULT_TEMPLATES: Record<string, string> = {
  "appointment.requested": "New visit request {{ref}} for {{when}}. Open the app to respond.",
  "appointment.confirmed": "Your visit {{ref}} on {{when}} is confirmed.",
  "appointment.declined": "Your visit request {{ref}} could not be accepted. Open the app to choose another nurse.",
  "appointment.cancelled": "Visit {{ref}} has been cancelled.",
  "appointment.rescheduled": "Visit {{ref}} has been moved to {{when}}.",
  "appointment.reminder": "Reminder: visit {{ref}} at {{when}}.",
  "appointment.status": "Update on visit {{ref}}: {{status}}.",
  "appointment.completed": "Visit {{ref}} is complete. Please share your feedback in the app.",
  "appointment.authorization": "Documents for visit {{ref}}: {{status}}.",
  "nurse.verification": "Your profile verification status: {{status}}.",
  "credential.expiring": "One of your credentials expires on {{date}}. Please upload a renewed copy.",
  "stay.requested": "New stay request {{ref}} for {{dates}}.",
  "stay.status": "Stay {{ref}} is now {{status}}.",
  "payment.status": "Payment for {{ref}}: {{status}}.",
  "refund.status": "Refund for {{ref}}: {{status}}.",
  "support.update": "Your support request has been updated.",
};

export const SUBJECTS: Record<string, string> = { "appointment.confirmed": "Visit confirmed", "appointment.reminder": "Visit reminder", "stay.status": "Stay update", "payment.status": "Payment update", "refund.status": "Refund update" };

export function render(body: string, vars: Record<string, string>) {
  return body.replace(/\{\{(\w+)\}\}/g, (_, k: string) => vars[k] ?? "");
}

/** Queues a notification on each channel. IN_APP is delivered immediately; others go through dispatchPending with retries. */
export async function notify(db: Db, userId: string, templateKey: string, vars: Record<string, string>, channels?: Channel[]) {
  const user = await db.user.findUnique({ where: { id: userId }, select: { preferredLanguage: true, email: true } });
  const chosen: Channel[] = channels ?? ["IN_APP", "SMS", ...(user?.email ? (["EMAIL"] as Channel[]) : []), ...((await isFeatureEnabled(db, "whatsapp_notifications")) ? (["WHATSAPP"] as Channel[]) : [])];
  for (const channel of chosen) {
    const lang = user?.preferredLanguage ?? "en";
    const tpl =
      (await db.notificationTemplate.findUnique({ where: { key_channel_language: { key: templateKey, channel, language: lang } } })) ??
      (await db.notificationTemplate.findUnique({ where: { key_channel_language: { key: templateKey, channel, language: "en" } } }));
    const body = render(tpl?.body ?? DEFAULT_TEMPLATES[templateKey] ?? templateKey, vars);
    await db.notification.create({ data: { userId, channel, templateKey, body, vars: vars as Prisma.InputJsonValue, status: channel === "IN_APP" ? "SENT" : "PENDING" } });
  }
}

async function deliver(db: Db, n: { channel: string; templateKey: string; body: string; vars: unknown; user: { phone: string; email: string | null; preferredLanguage: string } }) {
  const p = providers();
  if (n.channel === "SMS") return p.sms.send(n.user.phone, n.body);
  if (n.channel === "EMAIL") {
    if (!p.email) return { ok: false, skip: true, error: "email channel not configured" };
    if (!n.user.email) return { ok: false, skip: true, error: "no email address" };
    const tpl = await db.notificationTemplate.findFirst({ where: { key: n.templateKey, channel: "EMAIL" } });
    return p.email.send(n.user.email, tpl?.subject ?? SUBJECTS[n.templateKey] ?? "Update from HomeNurse India", n.body);
  }
  if (n.channel === "WHATSAPP") {
    if (!p.whatsapp) return { ok: false, skip: true, error: "whatsapp channel not configured" };
    return p.whatsapp.send(n.user.phone, n.templateKey.replaceAll(".", "_"), Object.values((n.vars ?? {}) as Record<string, string>), n.user.preferredLanguage);
  }
  return { ok: false, skip: true, error: `unknown channel ${n.channel}` };
}

/** Background dispatcher with bounded retries; delivery outcome is logged on the row. */
export async function dispatchPending(db: Db, maxAttempts = 3) {
  const pending = await db.notification.findMany({ where: { status: "PENDING", attempts: { lt: maxAttempts } }, include: { user: true }, take: 200, orderBy: { createdAt: "asc" } });
  let sent = 0;
  for (const n of pending) {
    let r: { ok: boolean; error?: string; skip?: boolean };
    try {
      r = await deliver(db, n);
    } catch (err) {
      r = { ok: false, error: String(err) };
      logger.warn("notification.dispatch_failed", { id: n.id, channel: n.channel });
    }
    const status = r.ok ? "SENT" : r.skip ? "SKIPPED" : n.attempts + 1 >= maxAttempts ? "FAILED" : "PENDING";
    await db.notification.update({ where: { id: n.id }, data: { attempts: { increment: 1 }, status, lastError: r.ok ? null : r.error } });
    if (r.ok) sent++;
  }
  return { processed: pending.length, sent };
}
