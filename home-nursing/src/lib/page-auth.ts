import { redirect } from "next/navigation";
import { currentPrincipal } from "./api";

/** Server-component guard. Pages are convenience only — every API route enforces permissions again. */
export async function requirePage(permission: string, next: string) {
  const p = await currentPrincipal();
  if (!p) redirect(`/login?next=${encodeURIComponent(next)}`);
  if (!p.permissions.has(permission)) redirect("/");
  return p;
}
