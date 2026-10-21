import { z } from "zod";
import { route } from "@/lib/api";
import { setRate } from "@/lib/domain/accommodation";

const d = z.string().regex(/^\d{4}-\d{2}-\d{2}$/);
export const POST = route(
  { permission: "property.manage", body: z.object({ nightlyInPaise: z.number().int().positive(), monthlyInPaise: z.number().int().positive().optional(), extendedStayDiscountPct: z.number().int().min(0).max(50).default(0), depositInPaise: z.number().int().min(0).default(0), validFrom: d, validTo: d.optional() }) },
  async ({ principal, params, body }) => setRate(principal!, params.id!, body),
);
