import { z } from "zod";
import { route } from "@/lib/api";
import { startPrescriptionUpload } from "@/lib/domain/appointments";

export const POST = route({ permission: "appointment.book", body: z.object({ kind: z.enum(["PRESCRIPTION", "CLINICIAN_ORDER"]), mimeType: z.string(), sizeBytes: z.number().int() }) }, async ({ principal, params, body }) =>
  startPrescriptionUpload(principal!, params.id!, body),
);
