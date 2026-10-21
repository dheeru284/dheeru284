import { env } from "@/lib/env";

/** Mock storage endpoint for local development only. Disabled in production. */
export async function PUT(req: Request) {
  if (env().NODE_ENV === "production") return new Response("Not found", { status: 404 });
  const u = new URL(req.url);
  const { MockStorageProvider } = await import("@/lib/providers/storage");
  const ok = new MockStorageProvider().verify("put", u.searchParams.get("key") ?? "", Number(u.searchParams.get("exp")), u.searchParams.get("sig") ?? "");
  return new Response(ok ? null : "Forbidden", { status: ok ? 204 : 403 });
}
