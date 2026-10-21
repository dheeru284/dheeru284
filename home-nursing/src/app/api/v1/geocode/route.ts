import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { providers } from "@/lib/providers";
import { rateLimit } from "@/lib/rate-limit";

/** Server-side geocoding so the maps API key never reaches the browser. */
export const GET = route({ permission: "authenticated" }, async ({ principal, url }) => {
  const q = (url.searchParams.get("q") ?? "").trim().slice(0, 200);
  if (q.length < 3) return { provider: providers().geocoding.name, results: [] };
  await rateLimit(prisma, `geo:${principal!.userId}`, 60, 3600);
  return { provider: providers().geocoding.name, results: await providers().geocoding.search(q) };
});
