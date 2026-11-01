import "server-only";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { API_PREFIX, apiBaseUrl } from "./api";

export const TOKEN_COOKIE = "bnip_token";

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
  }
}

export async function getToken(): Promise<string | undefined> {
  return (await cookies()).get(TOKEN_COOKIE)?.value;
}

type RequestOptions = {
  method?: string;
  json?: unknown;
  form?: FormData;
  headers?: Record<string, string>;
  /** Redirect to /login on 401 (pages). Actions pass false and handle it. */
  redirectOn401?: boolean;
};

/** Server-side call to the FastAPI backend with the user's token. Never runs in the browser. */
export async function api<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const token = await getToken();
  if (!token && opts.redirectOn401 !== false) redirect("/login");
  const headers: Record<string, string> = { ...(opts.headers ?? {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (opts.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.json);
  } else if (opts.form) {
    body = opts.form;
  }
  let res: Response;
  try {
    res = await fetch(`${apiBaseUrl()}${API_PREFIX}${path}`, {
      method: opts.method ?? "GET",
      headers,
      body,
      cache: "no-store",
    });
  } catch (err) {
    throw new ApiError(503, `Backend unreachable: ${err instanceof Error ? err.message : String(err)}`);
  }
  if (res.status === 401 && opts.redirectOn401 !== false) redirect("/login");
  const text = await res.text();
  const data: unknown = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const problem = (data ?? {}) as { detail?: unknown; title?: string };
    const detail =
      typeof problem.detail === "string" ? problem.detail : problem.title ?? `HTTP ${res.status}`;
    throw new ApiError(res.status, detail);
  }
  return data as T;
}
