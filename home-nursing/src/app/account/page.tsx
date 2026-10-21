import { requirePage } from "@/lib/page-auth";
import { AccountView } from "./AccountView";
export const dynamic = "force-dynamic";
export default async function Page() {
  await requirePage("privacy.self", "/account");
  return <AccountView />;
}
