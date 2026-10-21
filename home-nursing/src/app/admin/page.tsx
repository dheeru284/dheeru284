import { requirePage } from "@/lib/page-auth";
import { AdminConsole } from "./AdminConsole";

export const dynamic = "force-dynamic";

export default async function Page() {
  const p = await requirePage("admin.access", "/admin");
  return <AdminConsole permissions={[...p.permissions]} />;
}
