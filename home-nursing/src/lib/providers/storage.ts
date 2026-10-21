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

/** S3-compatible private bucket (AWS S3, Cloudflare R2, MinIO). Bucket must block all public access. */
export class S3StorageProvider implements StorageProvider {
  readonly name = "s3";
  private client: import("@aws-sdk/client-s3").S3Client | undefined;
  constructor(private cfg: { bucket: string; region: string; endpoint?: string; accessKeyId?: string; secretAccessKey?: string }) {}
  private async s3() {
    if (this.client) return this.client;
    const { S3Client } = await import("@aws-sdk/client-s3");
    this.client = new S3Client({
      region: this.cfg.region,
      endpoint: this.cfg.endpoint,
      forcePathStyle: !!this.cfg.endpoint,
      credentials: this.cfg.accessKeyId && this.cfg.secretAccessKey ? { accessKeyId: this.cfg.accessKeyId, secretAccessKey: this.cfg.secretAccessKey } : undefined,
    });
    return this.client;
  }
  async presignUpload(key: string, mimeType: string, ttlSec = 300) {
    const { PutObjectCommand } = await import("@aws-sdk/client-s3");
    const { getSignedUrl } = await import("@aws-sdk/s3-request-presigner");
    const url = await getSignedUrl(await this.s3(), new PutObjectCommand({ Bucket: this.cfg.bucket, Key: key, ContentType: mimeType, ServerSideEncryption: "AES256" }), { expiresIn: ttlSec });
    return { url, key, expiresAt: new Date(Date.now() + ttlSec * 1000) };
  }
  async presignDownload(key: string, ttlSec = 120) {
    const { GetObjectCommand } = await import("@aws-sdk/client-s3");
    const { getSignedUrl } = await import("@aws-sdk/s3-request-presigner");
    const url = await getSignedUrl(await this.s3(), new GetObjectCommand({ Bucket: this.cfg.bucket, Key: key }), { expiresIn: ttlSec });
    return { url, expiresAt: new Date(Date.now() + ttlSec * 1000) };
  }
}
