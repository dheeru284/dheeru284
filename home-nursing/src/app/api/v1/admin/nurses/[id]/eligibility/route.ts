import { z } from "zod";
import { route } from "@/lib/api";
import { approveServiceEligibility } from "@/lib/domain/credentials";

export const POST = route({ permission: "nurse.verify", body: z.object({ serviceId: z.string() }) }, async ({ principal, params, body }) => approveServiceEligibility(principal!, params.id!, body.serviceId));
