import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { PRIVACY_NOTICE_VERSION, recordConsent, withdrawConsent } from "@/lib/domain/privacy";

const PURPOSES = ["care_delivery", "share_with_nurse", "marketing", "whatsapp_updates"] as const;

export const GET = route({ permission: "privacy.self" }, async ({ principal }) => ({ noticeVersion: PRIVACY_NOTICE_VERSION, consents: await prisma.patientConsent.findMany({ where: { userId: principal!.userId }, orderBy: { grantedAt: "desc" } }) }));
export const POST = route({ permission: "privacy.self", body: z.object({ purpose: z.enum(PURPOSES), patientId: z.string().optional() }) }, async ({ principal, body }) => recordConsent(principal!, body.purpose, body.patientId));
export const DELETE = route({ permission: "privacy.self", body: z.object({ consentId: z.string() }) }, async ({ principal, body }) => { await withdrawConsent(principal!, body.consentId); return { ok: true }; });
