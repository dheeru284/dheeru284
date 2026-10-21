import { z } from "zod";
import { route } from "@/lib/api";
import { prisma } from "@/lib/db";
import { getSetting, updateSetting } from "@/lib/domain/settings";

export const GET = route({ permission: "admin.access" }, async () => ({ matching: await getSetting(prisma, "matching"), commerce: await getSetting(prisma, "commerce") }));

export const PUT = route({ permission: "settings.write", body: z.object({ key: z.enum(["matching", "commerce"]), patch: z.record(z.unknown()) }) }, async ({ principal, body }) =>
  updateSetting(prisma, body.key, body.patch, principal!.userId),
);
