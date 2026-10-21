import { z } from "zod";
import { route } from "@/lib/api";
import { extendStay } from "@/lib/domain/accommodation";

export const POST = route({ permission: "accommodation.book", body: z.object({ checkOut: z.string().regex(/^\d{4}-\d{2}-\d{2}$/) }) }, async ({ principal, params, body }) => extendStay(principal!, params.id!, body.checkOut));
