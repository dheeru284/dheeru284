import { createHmac, randomBytes, timingSafeEqual } from "node:crypto";

export type CreateOrderResult = { providerOrderId: string; amountInPaise: number; currency: "INR"; checkout: Record<string, unknown> };

export interface PaymentProvider {
  readonly name: string;
  createOrder(input: { amountInPaise: number; receipt: string; notes?: Record<string, string> }): Promise<CreateOrderResult>;
  /** Server-side verification of a client-reported payment. Never trust the client alone. */
  verifyPaymentSignature(input: { orderId: string; paymentId: string; signature: string }): boolean;
  verifyWebhook(rawBody: string, signature: string | null): boolean;
  refund(input: { paymentId: string; amountInPaise: number }): Promise<{ providerRefundId: string }>;
}

const safeEq = (a: string, b: string) => a.length === b.length && timingSafeEqual(Buffer.from(a), Buffer.from(b));

/** Razorpay signature scheme: HMAC_SHA256(order_id|payment_id, key_secret); webhooks: HMAC_SHA256(body, webhook_secret). */
export class RazorpayProvider implements PaymentProvider {
  readonly name = "razorpay";
  constructor(private keyId: string, private keySecret: string, private webhookSecret: string, private fetchImpl: typeof fetch = fetch) {}
  private auth() {
    return "Basic " + Buffer.from(`${this.keyId}:${this.keySecret}`).toString("base64");
  }
  async createOrder({ amountInPaise, receipt, notes }: { amountInPaise: number; receipt: string; notes?: Record<string, string> }) {
    const res = await this.fetchImpl("https://api.razorpay.com/v1/orders", {
      method: "POST",
      headers: { Authorization: this.auth(), "Content-Type": "application/json" },
      body: JSON.stringify({ amount: amountInPaise, currency: "INR", receipt, notes }),
    });
    if (!res.ok) throw new Error(`razorpay order failed: ${res.status}`);
    const o = (await res.json()) as { id: string };
    return { providerOrderId: o.id, amountInPaise, currency: "INR" as const, checkout: { key: this.keyId, order_id: o.id } };
  }
  verifyPaymentSignature({ orderId, paymentId, signature }: { orderId: string; paymentId: string; signature: string }) {
    const expected = createHmac("sha256", this.keySecret).update(`${orderId}|${paymentId}`).digest("hex");
    return safeEq(expected, signature);
  }
  verifyWebhook(rawBody: string, signature: string | null) {
    if (!signature) return false;
    return safeEq(createHmac("sha256", this.webhookSecret).update(rawBody).digest("hex"), signature);
  }
  async refund({ paymentId, amountInPaise }: { paymentId: string; amountInPaise: number }) {
    const res = await this.fetchImpl(`https://api.razorpay.com/v1/payments/${paymentId}/refund`, {
      method: "POST",
      headers: { Authorization: this.auth(), "Content-Type": "application/json" },
      body: JSON.stringify({ amount: amountInPaise }),
    });
    if (!res.ok) throw new Error(`razorpay refund failed: ${res.status}`);
    return { providerRefundId: ((await res.json()) as { id: string }).id };
  }
}

/** DEVELOPMENT ONLY. Same signature contract as Razorpay, with a local secret; moves no money. */
export class MockPaymentProvider implements PaymentProvider {
  readonly name = "mock";
  constructor(readonly secret = "mock-payment-secret") {}
  async createOrder({ amountInPaise }: { amountInPaise: number }) {
    const id = "order_mock_" + randomBytes(6).toString("hex");
    return { providerOrderId: id, amountInPaise, currency: "INR" as const, checkout: { mock: true, order_id: id } };
  }
  sign(orderId: string, paymentId: string) {
    return createHmac("sha256", this.secret).update(`${orderId}|${paymentId}`).digest("hex");
  }
  verifyPaymentSignature({ orderId, paymentId, signature }: { orderId: string; paymentId: string; signature: string }) {
    return safeEq(this.sign(orderId, paymentId), signature);
  }
  verifyWebhook(rawBody: string, signature: string | null) {
    return !!signature && safeEq(createHmac("sha256", this.secret).update(rawBody).digest("hex"), signature);
  }
  async refund() {
    return { providerRefundId: "rfnd_mock_" + randomBytes(6).toString("hex") };
  }
}
