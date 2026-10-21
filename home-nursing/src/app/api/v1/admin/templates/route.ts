import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { AppError } from "@/lib/errors";
import { audit } from "@/lib/domain/audit";

// Coarse guard against putting clinical details in notifications that may appear on lock screens or SMS.
const CLINICAL = /\b(diagnos|cancer|hiv|diabet|injection|catheter|prescription|medicine|surgery|pregnan|psychiatr)/i;

export const GET = route({ permission: "templates.manage" }, async () => prisma.notificationTemplate.findMany({ orderBy: [{ key: "asc" }, { channel: "asc" }, { language: "asc" }] }));

export const PUT = route(
  { permission: "templates.manage", body: z.object({ key: z.string(), channel: z.enum(["IN_APP", "SMS", "EMAIL", "WHATSAPP"]), language: z.string().min(2).max(5), subject: z.string().max(120).optional(), body: z.string().min(3).max(1000) }) },
  async ({ principal, body }) => {
    if (body.channel !== "IN_APP" && CLINICAL.test(body.body)) throw new AppError("VALIDATION", "Templates sent outside the app must not include clinical details");
    const t = await prisma.notificationTemplate.upsert({ where: { key_channel_language: { key: body.key, channel: body.channel, language: body.language } }, create: body, update: { body: body.body, subject: body.subject } });
    await audit(prisma, { actorUserId: principal!.userId, action: "template.update", entityType: "NotificationTemplate", entityId: t.id });
    return t;
  },
);
