import { z } from "zod";
import { route } from "@/lib/api";
import { startCredentialUpload } from "@/lib/domain/credentials";

export const POST = route(
  { permission: "nurse.self", body: z.object({ kind: z.enum(["REGISTRATION_CERT", "QUALIFICATION_CERT", "ID_PROOF", "PHOTO"]), mimeType: z.string(), sizeBytes: z.number().int(), expiresOn: z.string().optional() }) },
  async ({ principal, body }) => startCredentialUpload(principal!, { ...body, expiresOn: body.expiresOn ? new Date(body.expiresOn) : undefined, mandatory: body.kind !== "PHOTO" }),
);
