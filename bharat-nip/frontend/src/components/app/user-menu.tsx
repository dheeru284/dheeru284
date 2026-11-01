import Link from "next/link";

import { logout } from "@/app/actions";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ApiError, api, getToken } from "@/lib/server-api";
import type { User } from "@/lib/types";

export async function UserMenu() {
  if (!(await getToken())) {
    return (
      <Link href="/login" className="text-sm font-medium">
        Sign in
      </Link>
    );
  }
  let user: User;
  try {
    user = await api<User>("/auth/me", { redirectOn401: false });
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      return (
        <Link href="/login" className="text-sm font-medium">
          Session expired, sign in
        </Link>
      );
    }
    return <span className="text-xs text-muted-foreground">backend unavailable</span>;
  }
  return (
    <form action={logout} className="flex items-center gap-2">
      <span className="hidden text-sm sm:inline">{user.display_name}</span>
      <Badge variant="outline">{user.role}</Badge>
      <Button variant="ghost" size="sm" type="submit">
        Sign out
      </Button>
    </form>
  );
}
