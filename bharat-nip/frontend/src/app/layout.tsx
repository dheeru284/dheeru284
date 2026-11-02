import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { UserMenu } from "@/components/app/user-menu";
import "./globals.css";

export const metadata: Metadata = {
  title: "Bharat Narrative Intelligence",
  description: "Evidence-first fact-checking and narrative intelligence platform.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex min-h-full flex-col">
        <header className="border-b">
          <nav className="mx-auto flex w-full max-w-5xl flex-wrap items-center gap-x-5 gap-y-2 px-4 py-3 sm:px-6">
            <Link href="/" className="font-semibold">
              BNIP
            </Link>
            <Link href="/submit" className="text-sm text-muted-foreground hover:text-foreground">
              Submit
            </Link>
            <Link href="/claims" className="text-sm text-muted-foreground hover:text-foreground">
              Claims
            </Link>
            <Link href="/review" className="text-sm text-muted-foreground hover:text-foreground">
              Review
            </Link>
            <Link href="/narratives" className="text-sm text-muted-foreground hover:text-foreground">
              Narratives
            </Link>
            <Link href="/organization" className="text-sm text-muted-foreground hover:text-foreground">
              Organization
            </Link>
            <Link href="/tasks" className="text-sm text-muted-foreground hover:text-foreground">
              Tasks
            </Link>
            <div className="ml-auto">
              <Suspense fallback={null}>
                <UserMenu />
              </Suspense>
            </div>
          </nav>
        </header>
        {children}
      </body>
    </html>
  );
}
