import type { Metadata, Viewport } from "next";
import Link from "next/link";
import "./globals.css";
import { Header, currentLang } from "@/components/Header";
import { SwRegister } from "@/components/SwRegister";
import { t } from "@/lib/i18n";

export const metadata: Metadata = { title: "HomeNurse India — verified home nursing", description: "Book verified registered nurses at home and find stays near hospitals.", manifest: "/manifest.webmanifest", icons: { icon: "/icon.svg" } };
export const viewport: Viewport = { themeColor: "#17705f", width: "device-width", initialScale: 1 };

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const lang = await currentLang();
  return (
    <html lang={lang}>
      <body className="min-h-screen">
        <div className="bg-alert-600 px-4 py-2 text-center text-sm text-white" role="note">
          {t(lang, "emergency")} <a href="tel:112" className="font-bold underline">112</a> {t(lang, "emergencyTail")}
        </div>
        <SwRegister />
        <Header />
        <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
        <footer className="mt-16 border-t border-slate-200 bg-white">
          <div className="mx-auto grid max-w-6xl gap-6 px-4 py-8 text-sm sm:grid-cols-3">
            <div><p className="font-semibold">HomeNurse India</p><p className="muted mt-1">Working name. Non-emergency home nursing marketplace.</p></div>
            <ul className="space-y-1">
              {[["/how-it-works", "How it works"], ["/about", "About"], ["/contact", "Contact & support"], ["/safety", "Safety & emergencies"]].map(([h, l]) => <li key={h}><Link href={h!} className="hover:underline">{l}</Link></li>)}
            </ul>
            <ul className="space-y-1">
              {[["/privacy", "Privacy policy"], ["/terms", "Terms"], ["/refunds", "Cancellation & refunds"], ["/join/nurse", "Join as a nurse"], ["/join/partner", "List your property"]].map(([h, l]) => <li key={h}><Link href={h!} className="hover:underline">{l}</Link></li>)}
            </ul>
          </div>
        </footer>
      </body>
    </html>
  );
}
