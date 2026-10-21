import Link from "next/link";
import { cookies } from "next/headers";
import { currentPrincipal } from "@/lib/api";
import { prisma } from "@/lib/db";
import { t } from "@/lib/i18n";
import { LogoutButton } from "./LogoutButton";
import { LanguagePicker } from "./LanguagePicker";

export async function currentLang() {
  const p = await currentPrincipal().catch(() => null);
  if (p) {
    const u = await prisma.user.findUnique({ where: { id: p.userId }, select: { preferredLanguage: true } });
    if (u) return u.preferredLanguage;
  }
  return (await cookies()).get("hn_lang")?.value ?? "en";
}

export async function Header() {
  const p = await currentPrincipal().catch(() => null);
  const lang = await currentLang();
  const links: { href: string; label: string }[] = [];
  if (p?.roles.includes("PATIENT")) links.push({ href: "/patient", label: t(lang, "myCare") }, { href: "/patient/book", label: t(lang, "book") });
  if (p?.roles.includes("NURSE")) links.push({ href: "/nurse", label: t(lang, "nursePortal") });
  if (p?.roles.includes("ACCOMMODATION_PARTNER")) links.push({ href: "/partner", label: t(lang, "partnerPortal") });
  if (p?.permissions.has("admin.access")) links.push({ href: "/admin", label: t(lang, "admin") });
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
        <Link href="/" className="text-lg font-bold text-brand-700">HomeNurse<span className="text-ink-500"> India</span></Link>
        <nav className="flex flex-1 flex-wrap gap-x-4 gap-y-1 text-sm" aria-label="Main">
          <Link href="/services" className="hover:text-brand-700">{t(lang, "services")}</Link>
          <Link href="/stays" className="hover:text-brand-700">{t(lang, "stays")}</Link>
          <Link href="/hospitals" className="hover:text-brand-700">Hospitals</Link>
          <Link href="/verification" className="hover:text-brand-700">{t(lang, "verification")}</Link>
          {links.map((l) => <Link key={l.href} href={l.href} className="font-medium text-brand-700 hover:underline">{l.label}</Link>)}
        </nav>
        <div className="flex items-center gap-3 text-sm">
          <LanguagePicker current={lang} signedIn={!!p} />
          {p ? <><Link href="/account" className="hover:underline">{t(lang, "account")}</Link><LogoutButton label={t(lang, "signOut")} /></> : <Link href="/login" className="btn">{t(lang, "signIn")}</Link>}
        </div>
      </div>
    </header>
  );
}
