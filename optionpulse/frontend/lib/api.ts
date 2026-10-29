import type { Dashboard } from "./types";

export async function fetchDashboard(params: { symbol: string; asOf?: string }, signal?: AbortSignal): Promise<Dashboard> {
  const query = new URLSearchParams({ symbol: params.symbol, interval: "FIVE_MINUTE" });
  if (params.asOf) query.set("as_of", params.asOf);
  const res = await fetch(`/api/dashboard?${query}`, { cache: "no-store", signal });
  if (!res.ok) throw new Error(`Backend returned ${res.status}: ${await res.text()}`);
  return res.json();
}
