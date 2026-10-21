import { z } from "zod";
import { route } from "@/lib/api";
import { recordVisitNotes } from "@/lib/domain/appointments";

// Observations are recorded as entered. The software does not interpret them or suggest treatment.
const obs = z.object({ bpSystolic: z.number().int().min(40).max(300), bpDiastolic: z.number().int().min(20).max(200), pulse: z.number().int().min(20).max(250), tempC: z.number().min(30).max(45), spo2: z.number().int().min(50).max(100) }).partial();

export const POST = route({ permission: "visit.record", body: z.object({ notes: z.string().max(4000), observations: obs.optional() }) }, async ({ principal, params, body }) =>
  recordVisitNotes(principal!, params.id!, body.notes, body.observations),
);
