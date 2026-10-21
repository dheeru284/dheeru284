import { z } from "zod";
import { route } from "@/lib/api";
import { assignRole, setUserStatus } from "@/lib/domain/admin";

export const POST = route(
  { permission: "users.manage", body: z.union([z.object({ action: z.literal("status"), status: z.enum(["ACTIVE", "SUSPENDED"]), reason: z.string().min(3) }), z.object({ action: z.literal("grant_role"), role: z.enum(["ADMIN", "COMPLIANCE_OFFICER", "SUPPORT_AGENT"]) })]) },
  async ({ principal, params, body }) => {
    if (body.action === "status") await setUserStatus(principal!, params.id!, body.status, body.reason);
    else await assignRole(principal!, params.id!, body.role);
    return { ok: true };
  },
);
