import { errorResponse, ok } from "@/lib/api";
import { handlePaymentWebhook } from "@/lib/domain/payments";

// Raw body is required for signature verification, so this route does not use the JSON wrapper.
export async function POST(req: Request) {
  try {
    const raw = await req.text();
    return ok(await handlePaymentWebhook(raw, req.headers.get("x-razorpay-signature")));
  } catch (e) {
    return errorResponse(e);
  }
}
