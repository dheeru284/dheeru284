import { prisma } from "@/lib/db";
import { providers } from "@/lib/providers";

/** Property photos are not sensitive, but storage stays private; serve via short-lived signed redirect for verified listings only. */
export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const img = await prisma.propertyImage.findFirst({ where: { id, property: { verificationStatus: "VERIFIED", isActive: true } } });
  if (!img) return new Response("Not found", { status: 404 });
  if (img.url) return Response.redirect(img.url, 302);
  const { url } = await providers().storage.presignDownload(img.storageKey!, 300);
  return new Response(null, { status: 302, headers: { location: url, "cache-control": "private, max-age=240" } });
}
