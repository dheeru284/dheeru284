import { route } from "@/lib/api";
import { AppError } from "@/lib/errors";
import { partnerCalendar } from "@/lib/domain/accommodation";

export const GET = route({ permission: "property.manage" }, async ({ principal, params, url }) => {
  const from = url.searchParams.get("from"), to = url.searchParams.get("to");
  if (!from || !to) throw new AppError("VALIDATION", "from and to are required");
  return partnerCalendar(principal!, params.id!, from, to);
});
