import type { Metadata, Viewport } from "next";
import Link from "next/link";
import "./globals.css";
import { Header } from "@/components/Header";

export const metadata: Metadata = { title: "HomeNurse India — verified home nursing", description: "Book verified registered nurses at home and find stays near hospitals.", manifest: "/manifest.webmanifest" };
export const viewport: Viewport = { themeColor: "#17705f", width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <div className="bg-alert-600 px-4 py-2 text-center text-sm text-white" role="note">
          This is not an emergency service. In a medical emergency call <a href="tel:112" className="font-bold underline">112</a> or go to the nearest hospital.
        </div>
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
