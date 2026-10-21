import { route } from "@/lib/api";
import { reconciliationReport } from "@/lib/domain/payments";

export const GET = route({ permission: "payments.manage" }, async ({ principal }) => reconciliationReport(principal!));
