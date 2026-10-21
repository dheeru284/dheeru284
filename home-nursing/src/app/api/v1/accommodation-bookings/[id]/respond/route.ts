import { z } from "zod";
import { route } from "@/lib/api";
import { partnerRespond } from "@/lib/domain/accommodation";

export const POST = route({ permission: "stay.partner", body: z.object({ decision: z.enum(["CONFIRMED", "DECLINED"]) }) }, async ({ principal, params, body }) => partnerRespond(principal!, params.id!, body.decision));
