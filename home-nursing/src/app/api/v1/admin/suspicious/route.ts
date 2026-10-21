import { route } from "@/lib/api";
import { suspiciousActivity } from "@/lib/domain/admin";

export const GET = route({ permission: "complaint.manage" }, async ({ principal }) => suspiciousActivity(principal!));
