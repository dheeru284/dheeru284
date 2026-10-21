import { z } from "zod";
import { route } from "@/lib/api";
import { addBlackout, removeBlackout } from "@/lib/domain/accommodation";

const d = z.string().regex(/^\d{4}-\d{2}-\d{2}$/);
export const POST = route({ permission: "property.manage", body: z.object({ startDate: d, endDate: d, reason: z.string().max(100).optional() }) }, async ({ principal, params, body }) => addBlackout(principal!, params.id!, body.startDate, body.endDate, body.reason));
export const DELETE = route({ permission: "property.manage", body: z.object({ blackoutId: z.string() }) }, async ({ principal, body }) => { await removeBlackout(principal!, body.blackoutId); return { ok: true }; });
