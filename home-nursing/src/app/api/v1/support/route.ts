import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";

export const POST = route(
  {
    permission: "support.write",
    body: z.discriminatedUnion("type", [
      z.object({ type: z.literal("ticket"), subject: z.string().min(3).max(120), body: z.string().min(5).max(4000) }),
      z.object({ type: z.literal("complaint"), category: z.string().max(60), severity: z.enum(["NORMAL", "SERIOUS", "CRITICAL"]).default("NORMAL"), description: z.string().min(10).max(4000), appointmentId: z.string().optional(), accommodationBookingId: z.string().optional() }),
      z.object({ type: z.literal("incident"), kind: z.enum(["SAFETY", "CLINICAL", "PRIVACY", "SECURITY"]), description: z.string().min(10).max(4000), appointmentId: z.string().optional() }),
    ]),
  },
  async ({ principal, body }) => {
    const uid = principal!.userId;
    if (body.type === "ticket") return prisma.supportTicket.create({ data: { userId: uid, subject: body.subject, body: body.body } });
    if (body.type === "complaint") {
      const { type: _t, ...c } = body;
      return prisma.complaint.create({ data: { ...c, raisedByUserId: uid } });
    }
    const { type: _t, ...i } = body;
    return prisma.incident.create({ data: { ...i, reportedByUserId: uid } });
  },
);
