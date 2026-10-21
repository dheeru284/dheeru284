import type { Db } from "./db";
import { AppError } from "./errors";

/** Fixed-window limiter in Postgres (single atomic upsert). Swap for Redis when traffic warrants it. */
export async function rateLimit(db: Db, key: string, max: number, windowSec: number) {
  const rows = await db.$queryRaw<{ count: number }[]>`
    INSERT INTO "RateLimitBucket" ("key", "count", "windowEnd")
    VALUES (${key}, 1, now() + make_interval(secs => ${windowSec}))
    ON CONFLICT ("key") DO UPDATE SET
      "count" = CASE WHEN "RateLimitBucket"."windowEnd" < now() THEN 1 ELSE "RateLimitBucket"."count" + 1 END,
      "windowEnd" = CASE WHEN "RateLimitBucket"."windowEnd" < now() THEN now() + make_interval(secs => ${windowSec}) ELSE "RateLimitBucket"."windowEnd" END
    RETURNING "count"`;
  if (rows[0]!.count > max) throw new AppError("RATE_LIMITED", "Too many requests. Please try again later.");
}
