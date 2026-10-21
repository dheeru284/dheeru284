import type { Db } from "../db";
import { AppError } from "../errors";

const CLEARED = ["SATISFIED", "EXCEPTION_RECORDED"];

/** Blocks an operation in a jurisdiction when a configured mandatory approval is outstanding. Nothing is hardcoded as universally mandatory. */
export async function assertOperationAllowed(db: Db, operation: "NURSING_BOOKINGS" | "ACCOMMODATION_BOOKINGS", state?: string) {
  const blockers = await db.complianceItem.findMany({
    where: { blocksOperation: operation, jurisdiction: { in: ["IN", ...(state ? [state] : [])] }, status: { notIn: CLEARED } },
    select: { id: true, requirement: true, jurisdiction: true },
  });
  if (blockers.length) throw new AppError("COMPLIANCE_BLOCKED", "This service is temporarily unavailable in your area.", { blockers: blockers.map((b) => b.id) });
}
