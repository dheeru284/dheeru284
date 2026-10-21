import { z } from "zod";
import { route } from "@/lib/api";
import { setNurseStatus } from "@/lib/domain/credentials";

export const POST = route({ permission: "nurse.verify", body: z.object({ status: z.enum(["APPROVED", "REJECTED", "SUSPENDED", "PENDING_VERIFICATION"]), reason: z.string().max(500).optional() }) }, async ({ principal, params, body }) =>
  setNurseStatus(principal!, params.id!, body.status, body.reason),
);
