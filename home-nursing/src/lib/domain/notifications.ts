import type { Db } from "../db";
import { logger } from "../logger";
import { providers } from "../providers";

/** Template keys → default English bodies. Bodies must never include diagnoses, procedures or medical details. */
export const DEFAULT_TEMPLATES: Record<string, string> = {
  "appointment.requested": "New visit request {{ref}} for {{when}}. Open the app to respond.",
  "appointment.confirmed": "Your visit {{ref}} on {{when}} is confirmed.",
  "appointment.declined": "Your visit request {{ref}} could not be accepted. Open the app to choose another nurse.",
  "appointment.cancelled": "Visit {{ref}} has been cancelled.",
  "appointment.reminder": "Reminder: visit {{ref}} at {{when}}.",
  "appointment.status": "Update on visit {{ref}}: {{status}}.",
  "appointment.completed": "Visit {{ref}} is complete. Please share your feedback in the app.",
  "nurse.verification": "Your profile verification status: {{status}}.",
  "credential.expiring": "One of your credentials expires on {{date}}. Please upload a renewed copy.",
  "stay.requested": "New stay request {{ref}} for {{dates}}.",
  "stay.status": "Stay {{ref}} is now {{status}}.",
  "payment.status": "Payment for {{ref}}: {{status}}.",
  "support.update": "Your support request has been updated.",
};

export function render(body: string, vars: Record<string, string>) {
  return body.replace(/\{\{(\w+)\}\}/g, (_, k: string) => vars[k] ?? "");
}

export async function notify(db: Db, userId: string, templateKey: string, vars: Record<string, string>, channels: ("IN_APP" | "SMS")[] = ["IN_APP", "SMS"]) {
  const user = await db.user.findUnique({ where: { id: userId }, select: { preferredLanguage: true } });
  for (const channel of channels) {
    const tpl =
      (await db.notificationTemplate.findUnique({ where: { key_channel_language: { key: templateKey, channel, language: user?.preferredLanguage ?? "en" } } })) ??
      (await db.notificationTemplate.findUnique({ where: { key_channel_language: { key: templateKey, channel, language: "en" } } }));
    const body = render(tpl?.body ?? DEFAULT_TEMPLATES[templateKey] ?? templateKey, vars);
    await db.notification.create({ data: { userId, channel, templateKey, body, status: channel === "IN_APP" ? "SENT" : "PENDING" } });
  }
}

/** Background dispatcher with bounded retries; delivery outcome is logged on the row. */
export async function dispatchPending(db: Db, maxAttempts = 3) {
  const pending = await db.notification.findMany({ where: { status: "PENDING", attempts: { lt: maxAttempts } }, include: { user: true }, take: 100 });
  let sent = 0;
  for (const n of pending) {
    try {
      const r = n.channel === "SMS" ? await providers().sms.send(n.user.phone, n.body) : { ok: false, error: `channel ${n.channel} not configured` };
      await db.notification.update({ where: { id: n.id }, data: { attempts: { increment: 1 }, status: r.ok ? "SENT" : n.attempts + 1 >= maxAttempts ? "FAILED" : "PENDING", lastError: r.ok ? null : r.error } });
      if (r.ok) sent++;
    } catch (err) {
      logger.warn("notification.dispatch_failed", { id: n.id });
      await db.notification.update({ where: { id: n.id }, data: { attempts: { increment: 1 }, lastError: String(err), status: n.attempts + 1 >= maxAttempts ? "FAILED" : "PENDING" } });
    }
  }
  return { processed: pending.length, sent };
}
