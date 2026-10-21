import { z } from "zod";
import { route } from "@/lib/api";
import { confirmPayment } from "@/lib/domain/payments";

export const POST = route({ permission: "authenticated", body: z.object({ providerOrderId: z.string(), providerPaymentId: z.string(), signature: z.string() }) }, async ({ body }) => confirmPayment(body));
