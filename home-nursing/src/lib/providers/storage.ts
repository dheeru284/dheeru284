import { createHmac, randomUUID } from "node:crypto";

export const ALLOWED_UPLOADS: Record<string, string[]> = {
  CREDENTIAL: ["application/pdf", "image/jpeg", "image/png"],
  PRESCRIPTION: ["application/pdf", "image/jpeg", "image/png"],
  PHOTO: ["image/jpeg", "image/png", "image/webp"],
};
export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

export interface StorageProvider {
  readonly name: string;
  /** Short-lived signed URL for a direct upload to a PRIVATE bucket. */
  presignUpload(key: string, mimeType: string, ttlSec?: number): Promise<{ url: string; key: string; expiresAt: Date }>;
  presignDownload(key: string, ttlSec?: number): Promise<{ url: string; expiresAt: Date }>;
}

export function newObjectKey(prefix: string, mimeType: string) {
  const ext = mimeType.split("/")[1] ?? "bin";
  return `${prefix}/${randomUUID()}.${ext}`;
}

/** DEVELOPMENT ONLY. Issues HMAC-signed local URLs; nothing is publicly listable. */
export class MockStorageProvider implements StorageProvider {
  readonly name = "mock";
  constructor(private secret = "mock-storage-secret", private base = "/api/v1/dev-storage") {}
  private sign(key: string, exp: number, op: string) {
    return createHmac("sha256", this.secret).update(`${op}|${key}|${exp}`).digest("hex");
  }
  async presignUpload(key: string, _mime: string, ttlSec = 300) {
    const exp = Date.now() + ttlSec * 1000;
    return { key, url: `${this.base}?op=put&key=${encodeURIComponent(key)}&exp=${exp}&sig=${this.sign(key, exp, "put")}`, expiresAt: new Date(exp) };
  }
  async presignDownload(key: string, ttlSec = 120) {
    const exp = Date.now() + ttlSec * 1000;
    return { url: `${this.base}?op=get&key=${encodeURIComponent(key)}&exp=${exp}&sig=${this.sign(key, exp, "get")}`, expiresAt: new Date(exp) };
  }
  verify(op: string, key: string, exp: number, sig: string) {
    return exp > Date.now() && this.sign(key, exp, op) === sig;
  }
}
