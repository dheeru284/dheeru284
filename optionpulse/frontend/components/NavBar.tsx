"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { fetchHealth } from "@/lib/api";
import { SOURCE_LABEL } from "@/lib/format";

const LINKS = [
  { href: "/", label: "Today" },
  { href: "/strategies", label: "Strategies" },
  { href: "/performance", label: "Performance" },
];

export function NavBar() {
  const path = usePathname();
  const [source, setSource] = useState<string | null>(null);
  useEffect(() => { fetchHealth().then((h) => setSource(h.source)).catch(() => setSource("OFFLINE")); }, []);
  return (
    <header className="nav">
      <Link href="/" className="brand">
        <span className="logo" aria-hidden /> OptionPulse <span className="brand-ai">AI</span>
      </Link>
      <nav aria-label="Main">
        {LINKS.map((l) => (
          <Link key={l.href} href={l.href} className={path === l.href ? "active" : ""}>{l.label}</Link>
        ))}
      </nav>
      {source && (
        <span className={`pill source-${source.toLowerCase()}`} title="Where prices come from">
          <span className="pulse" aria-hidden />
          {source === "OFFLINE" ? "Backend offline" : SOURCE_LABEL[source] ?? source}
        </span>
      )}
    </header>
  );
}
