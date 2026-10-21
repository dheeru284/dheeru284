import Link from "next/link";
import { currentPrincipal } from "@/lib/api";
import { LogoutButton } from "./LogoutButton";

export async function Header() {
  const p = await currentPrincipal().catch(() => null);
  const links: { href: string; label: string }[] = [];
  if (p?.roles.includes("PATIENT")) links.push({ href: "/patient", label: "My care" }, { href: "/patient/book", label: "Book a nurse" });
  if (p?.roles.includes("NURSE")) links.push({ href: "/nurse", label: "Nurse portal" });
  if (p?.roles.includes("ACCOMMODATION_PARTNER")) links.push({ href: "/partner", label: "Partner portal" });
  if (p?.permissions.has("admin.access")) links.push({ href: "/admin", label: "Admin" });
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
        <Link href="/" className="text-lg font-bold text-brand-700">HomeNurse<span className="text-ink-500"> India</span></Link>
        <nav className="flex flex-1 flex-wrap gap-x-4 gap-y-1 text-sm" aria-label="Main">
          <Link href="/services" className="hover:text-brand-700">Services</Link>
          <Link href="/stays" className="hover:text-brand-700">Stays near hospitals</Link>
          <Link href="/verification" className="hover:text-brand-700">Nurse verification</Link>
          {links.map((l) => <Link key={l.href} href={l.href} className="font-medium text-brand-700 hover:underline">{l.label}</Link>)}
        </nav>
        {p ? <div className="flex items-center gap-3 text-sm"><Link href="/account" className="hover:underline">Account</Link><LogoutButton /></div> : <Link href="/login" className="btn">Sign in</Link>}
      </div>
    </header>
  );
}
