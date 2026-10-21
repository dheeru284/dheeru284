import { z } from "zod";
import { route } from "@/lib/api";
import { refundPayment } from "@/lib/domain/payments";

export const POST = route({ permission: "payments.manage", body: z.object({ paymentId: z.string(), amountInPaise: z.number().int().positive(), reason: z.string().min(3).max(500) }) }, async ({ principal, body }) =>
  refundPayment(principal!, body.paymentId, body.amountInPaise, body.reason),
);
