import { cookies, headers } from "next/headers";
import { NextResponse } from "next/server";
import { z, ZodError, type ZodTypeAny } from "zod";
import { prisma } from "./db";
import { env } from "./env";
import { AppError } from "./errors";
import { logger } from "./logger";
import { resolveSession, SESSION_COOKIE, type Principal } from "./auth/session";

type Ctx<B> = { principal: Principal | null; body: B; params: Record<string, string>; url: URL; req: Request };

type Options<S extends ZodTypeAny | undefined> = {
  /** Required permission. Omit for public endpoints; use "authenticated" for any signed-in user. */
  permission?: string;
  body?: S;
};

export function ok(data: unknown, status = 200) {
  return NextResponse.json({ data }, { status });
}

export function errorResponse(e: unknown) {
  if (e instanceof AppError) return NextResponse.json({ error: { code: e.code, message: e.message, details: e.details ?? null } }, { status: e.status });
  if (e instanceof ZodError) return NextResponse.json({ error: { code: "VALIDATION", message: "Invalid request", details: e.flatten() } }, { status: 400 });
  logger.error("api.unhandled", { err: e instanceof Error ? e.message : String(e) });
  return NextResponse.json({ error: { code: "INTERNAL", message: "Something went wrong" } }, { status: 500 });
}

/** Same-origin check for cookie-authenticated mutations (CSRF defence alongside SameSite=Lax). */
async function assertSameOrigin(req: Request) {
  if (["GET", "HEAD", "OPTIONS"].includes(req.method)) return;
  const origin = (await headers()).get("origin");
  if (!origin) return; // non-browser clients (no ambient cookies) — still require a session for protected routes
  const allowed = new URL(env().APP_URL).origin;
  const self = new URL(req.url).origin;
  if (origin !== allowed && origin !== self) throw new AppError("FORBIDDEN", "Cross-origin request rejected");
}

export async function currentPrincipal(): Promise<Principal | null> {
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  return resolveSession(prisma, token);
}

export function route<S extends ZodTypeAny | undefined = undefined>(
  opts: Options<S>,
  fn: (ctx: Ctx<S extends ZodTypeAny ? z.infer<S> : undefined>) => Promise<Response | unknown>,
) {
  return async (req: Request, routeCtx: { params: Promise<Record<string, string>> }) => {
    try {
      await assertSameOrigin(req);
      const principal = await currentPrincipal();
      if (opts.permission) {
        if (!principal) throw new AppError("UNAUTHENTICATED", "Please sign in");
        if (opts.permission !== "authenticated" && !principal.permissions.has(opts.permission)) throw new AppError("FORBIDDEN", "You do not have access to this action");
      }
      let body: unknown = undefined;
      if (opts.body) {
        const raw = await req.json().catch(() => {
          throw new AppError("VALIDATION", "Body must be JSON");
        });
        body = opts.body.parse(raw);
      }
      const result = await fn({ principal, body: body as never, params: (await routeCtx?.params) ?? {}, url: new URL(req.url), req });
      return result instanceof Response ? result : ok(result);
    } catch (e) {
      return errorResponse(e);
    }
  };
}

export function must(p: Principal | null): Principal {
  if (!p) throw new AppError("UNAUTHENTICATED", "Please sign in");
  return p;
}

export const pageParams = (url: URL) => {
  const take = Math.min(Math.max(Number(url.searchParams.get("limit") ?? 20), 1), 100);
  const skip = Math.max(Number(url.searchParams.get("offset") ?? 0), 0);
  return { take, skip };
};
