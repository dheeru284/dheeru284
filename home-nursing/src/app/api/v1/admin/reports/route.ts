import { route } from "@/lib/api";
import { AppError } from "@/lib/errors";
import { exportReport, REPORTS, type ReportKind } from "@/lib/domain/admin";

export const GET = route({ permission: "reports.export" }, async ({ principal, url }) => {
  const kind = url.searchParams.get("kind") as ReportKind;
  if (!REPORTS.includes(kind)) throw new AppError("VALIDATION", `kind must be one of ${REPORTS.join(", ")}`);
  const from = new Date(url.searchParams.get("from") ?? "2000-01-01"), to = new Date(url.searchParams.get("to") ?? "2100-01-01");
  const csv = await exportReport(principal!, kind, from, to);
  return new Response(csv, { headers: { "content-type": "text/csv; charset=utf-8", "content-disposition": `attachment; filename="${kind}.csv"`, "cache-control": "no-store" } });
});
