import type { Catalog, Overview, Performance } from "./types";

async function get<T>(path: string, params: Record<string, string | undefined> = {}, signal?: AbortSignal): Promise<T> {
  const query = new URLSearchParams(Object.entries(params).filter((e): e is [string, string] => e[1] !== undefined));
  const res = await fetch(`${path}${query.size ? `?${query}` : ""}`, { cache: "no-store", signal });
  if (!res.ok) {
    let detail = await res.text();
    try { detail = JSON.parse(detail).detail ?? detail; } catch { /* plain text */ }
    throw new Error(res.status === 502 ? detail : `Backend returned ${res.status}: ${detail}`);
  }
  return res.json();
}

export const fetchOverview = (signal?: AbortSignal) => get<Overview>("/api/portal/overview", { symbol: "NIFTY" }, signal);
export const fetchPerformance = (sessions: number, signal?: AbortSignal) =>
  get<Performance>("/api/portal/performance", { symbol: "NIFTY", sessions: String(sessions) }, signal);
export const fetchCatalog = (signal?: AbortSignal) => get<Catalog>("/api/portal/catalog", {}, signal);
export const fetchHealth = () => get<{ provider: string; source: string }>("/api/health");
