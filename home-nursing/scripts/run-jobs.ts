// Scheduled jobs entrypoint. Run from a scheduler (cron / Cloud Scheduler / k8s CronJob), e.g. every 5 minutes.
import { prisma } from "../src/lib/db";
import { logger } from "../src/lib/logger";
import { sweepCredentialExpiry } from "../src/lib/domain/credentials";
import { dispatchPending, notify } from "../src/lib/domain/notifications";
import { formatInTz } from "../src/lib/time";
import { applyRetention } from "../src/lib/domain/admin";

async function reminders() {
  const from = new Date(Date.now() + 23 * 3600_000), to = new Date(Date.now() + 24 * 3600_000);
  const appts = await prisma.appointment.findMany({ where: { status: "CONFIRMED", startAt: { gte: from, lt: to } }, include: { nurse: true } });
  for (const a of appts) {
    const already = await prisma.notification.count({ where: { templateKey: "appointment.reminder", body: { contains: a.reference } } });
    if (already) continue;
    await notify(prisma, a.bookedByUserId, "appointment.reminder", { ref: a.reference, when: formatInTz(a.startAt) });
    await notify(prisma, a.nurse.userId, "appointment.reminder", { ref: a.reference, when: formatInTz(a.startAt) });
  }
  return appts.length;
}

/** Requests nobody accepted before the start time are cancelled and the patient is told, rather than silently lingering. */
async function expireStaleRequests() {
  const stale = await prisma.appointment.findMany({ where: { status: { in: ["AWAITING_NURSE_ACCEPTANCE", "AWAITING_AUTHORIZATION"] }, startAt: { lt: new Date() } } });
  for (const a of stale) {
    const r = await prisma.appointment.updateMany({ where: { id: a.id, status: a.status }, data: { status: "CANCELLED", cancelReason: "not accepted before start time" } });
    if (r.count) {
      await prisma.appointmentStatusHistory.create({ data: { appointmentId: a.id, fromStatus: a.status, toStatus: "CANCELLED", note: "expired: not accepted before start time" } });
      await notify(prisma, a.bookedByUserId, "appointment.cancelled", { ref: a.reference });
    }
  }
  return stale.length;
}

async function main() {
  for (const [name, job] of [["credential-expiry", () => sweepCredentialExpiry(prisma)], ["reminders", reminders], ["notification-dispatch", () => dispatchPending(prisma)], ["retention", () => applyRetention(prisma)], ["stale-requests", expireStaleRequests]] as const) {
    try {
      logger.info("job.done", { job: name, result: (await job()) as never });
    } catch (e) {
      logger.error("job.failed", { job: name, err: String(e) }); // continue other jobs; exit code reflects failure
      process.exitCode = 1;
    }
  }
}
main().finally(() => prisma.$disconnect());
