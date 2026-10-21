import { z } from "zod";
import { route } from "@/lib/api";
import { env } from "@/lib/env";
import { AppError } from "@/lib/errors";
import { providers } from "@/lib/providers";
import { MockPaymentProvider } from "@/lib/providers/payments";
import { confirmPayment } from "@/lib/domain/payments";

/** DEVELOPMENT ONLY: plays the role of the payment gateway's checkout, then goes through normal server verification. */
export const POST = route({ permission: "appointment.book", body: z.object({ providerOrderId: z.string() }) }, async ({ body }) => {
  const p = providers().payments;
  if (env().NODE_ENV === "production" || !(p instanceof MockPaymentProvider)) throw new AppError("NOT_FOUND", "Not found");
  const paymentId = `pay_mock_${Date.now()}`;
  return confirmPayment({ providerOrderId: body.providerOrderId, providerPaymentId: paymentId, signature: p.sign(body.providerOrderId, paymentId) });
});
