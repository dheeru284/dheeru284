import { z } from "zod";
import { route } from "@/lib/api";
import { startPropertyPhotoUpload } from "@/lib/domain/accommodation";

export const POST = route({ permission: "property.manage", body: z.object({ mimeType: z.string(), sizeBytes: z.number().int(), alt: z.string().min(2).max(120) }) }, async ({ principal, params, body }) =>
  startPropertyPhotoUpload(principal!, params.id!, body.mimeType, body.sizeBytes, body.alt),
);
