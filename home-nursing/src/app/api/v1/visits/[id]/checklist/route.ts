import { z } from "zod";
import { route } from "@/lib/api";
import { updateChecklist } from "@/lib/domain/appointments";

export const POST = route({ permission: "visit.record", body: z.object({ itemKey: z.string(), done: z.boolean() }) }, async ({ principal, params, body }) => updateChecklist(principal!, params.id!, body.itemKey, body.done));
