/**
 * Typed client for the BNIP backend (API_DESIGN.md). Types mirror
 * backend/app/schemas/system.py. Only endpoints that exist are wrapped here.
 */

export type CheckResult = { ok: boolean; required: boolean; detail: string };

export type Readiness = {
  status: "ok" | "degraded";
  checks: Record<string, CheckResult>;
};

export type ProvidersInfo = {
  llm: { name: string; model: string; is_mock: boolean };
  embedding: { name: string; model: string; dimensions: number; is_mock: boolean };
};

export type SystemStatus =
  | { kind: "reachable"; httpStatus: number; readiness: Readiness; providers: ProvidersInfo }
  | { kind: "unreachable"; error: string };

export const API_PREFIX = "/api/v1";

export function apiBaseUrl(): string {
  return (process.env.BNIP_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");
}

function isReadiness(value: unknown): value is Readiness {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return (
    (v.status === "ok" || v.status === "degraded") &&
    typeof v.checks === "object" &&
    v.checks !== null
  );
}

function isProviders(value: unknown): value is ProvidersInfo {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return typeof v.llm === "object" && v.llm !== null && typeof v.embedding === "object";
}

/**
 * Fetch live readiness and provider configuration. Readiness returns 503 with a valid
 * body when a required dependency is down, so a 503 is still "reachable".
 */
export async function fetchSystemStatus(
  baseUrl: string = apiBaseUrl(),
  fetchImpl: typeof fetch = fetch,
): Promise<SystemStatus> {
  try {
    const [readyRes, providersRes] = await Promise.all([
      fetchImpl(`${baseUrl}${API_PREFIX}/health/ready`, { cache: "no-store" }),
      fetchImpl(`${baseUrl}${API_PREFIX}/system/providers`, { cache: "no-store" }),
    ]);
    const readiness: unknown = await readyRes.json();
    const providers: unknown = await providersRes.json();
    if (!isReadiness(readiness) || !providersRes.ok || !isProviders(providers)) {
      return { kind: "unreachable", error: "Backend returned an unexpected response." };
    }
    return { kind: "reachable", httpStatus: readyRes.status, readiness, providers };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return { kind: "unreachable", error: message };
  }
}
