import { pageParams, route } from "@/lib/api";
import { listUsers } from "@/lib/domain/admin";

export const GET = route({ permission: "users.manage" }, async ({ principal, url }) =>
  listUsers(principal!, { search: url.searchParams.get("q") ?? undefined, role: (url.searchParams.get("role") ?? undefined) as never, ...pageParams(url) }),
);
