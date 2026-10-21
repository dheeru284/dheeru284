import { z } from "zod";
import { route } from "@/lib/api";
import { partnerStayTransition } from "@/lib/domain/accommodation";

export const POST = route({ permission: "stay.partner", body: z.object({ to: z.enum(["CHECKED_IN", "COMPLETED", "CANCELLED"]), reason: z.string().max(500).optional() }) }, async ({ principal, params, body }) =>
  partnerStayTransition(principal!, params.id!, body.to, body.reason),
);
