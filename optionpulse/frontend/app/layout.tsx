import type { Metadata } from "next";
import { NavBar } from "@/components/NavBar";
import "./globals.css";

export const metadata: Metadata = {
  title: "OptionPulse AI",
  description: "NIFTY strategies, paper trades and market context in one calm place",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="glow" aria-hidden />
        <NavBar />
        <main>{children}</main>
        <footer className="site-footer">
          Paper trading only. OptionPulse never connects to a broker or places orders. Nothing here is investment advice.
        </footer>
      </body>
    </html>
  );
}
