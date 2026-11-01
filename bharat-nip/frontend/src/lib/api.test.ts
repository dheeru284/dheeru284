import { describe, expect, it } from "vitest";

import { fetchSystemStatus } from "./api";

const readyBody = {
  status: "degraded",
  checks: {
    database: { ok: true, required: true, detail: "connected" },
    llm_provider: { ok: false, required: false, detail: "ollama: unreachable" },
  },
};
const providersBody = {
  llm: { name: "ollama", model: "llama3.1:8b", is_mock: false },
  embedding: { name: "ollama", model: "nomic-embed-text", dimensions: 768, is_mock: false },
};

function fakeFetch(routes: Record<string, { status: number; body: unknown }>): typeof fetch {
  return (async (input: RequestInfo | URL) => {
    const url = String(input);
    const match = Object.entries(routes).find(([path]) => url.endsWith(path));
    if (!match) throw new Error(`unexpected url ${url}`);
    const [, { status, body }] = match;
    return new Response(JSON.stringify(body), { status });
  }) as typeof fetch;
}

describe("fetchSystemStatus", () => {
  it("returns readiness and providers when the backend answers", async () => {
    const result = await fetchSystemStatus(
      "http://api.test",
      fakeFetch({
        "/api/v1/health/ready": { status: 200, body: readyBody },
        "/api/v1/system/providers": { status: 200, body: providersBody },
      }),
    );
    expect(result.kind).toBe("reachable");
    if (result.kind === "reachable") {
      expect(result.readiness.checks.database.ok).toBe(true);
      expect(result.providers.llm.is_mock).toBe(false);
    }
  });

  it("treats a 503 readiness with a valid body as reachable", async () => {
    const result = await fetchSystemStatus(
      "http://api.test",
      fakeFetch({
        "/api/v1/health/ready": { status: 503, body: readyBody },
        "/api/v1/system/providers": { status: 200, body: providersBody },
      }),
    );
    expect(result).toMatchObject({ kind: "reachable", httpStatus: 503 });
  });

  it("reports unreachable on network failure instead of inventing a status", async () => {
    const failing = (async () => {
      throw new Error("ECONNREFUSED");
    }) as typeof fetch;
    const result = await fetchSystemStatus("http://api.test", failing);
    expect(result).toEqual({ kind: "unreachable", error: "ECONNREFUSED" });
  });

  it("rejects malformed responses", async () => {
    const result = await fetchSystemStatus(
      "http://api.test",
      fakeFetch({
        "/api/v1/health/ready": { status: 200, body: { hello: "world" } },
        "/api/v1/system/providers": { status: 200, body: providersBody },
      }),
    );
    expect(result.kind).toBe("unreachable");
  });
});
