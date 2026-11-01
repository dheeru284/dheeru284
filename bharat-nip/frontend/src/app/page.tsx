import Link from "next/link";
import { Suspense } from "react";

import { SystemStatus, SystemStatusSkeleton } from "@/components/system-status";

export default function Home() {
  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-10 sm:px-6">
      <header className="mb-8 grid gap-2">
        <p className="text-sm font-medium text-muted-foreground">Phase 1 · Evidence pipeline</p>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          Bharat Narrative Intelligence Platform
        </h1>
        <p className="text-muted-foreground">
          Evidence-first claim assessment. Verdicts are decided by evidence, never by who made the
          claim, and every conclusion must trace back to stored sources.
        </p>
      </header>

      <section aria-labelledby="status-heading" className="grid gap-3">
        <h2 id="status-heading" className="text-lg font-semibold">
          System status
        </h2>
        <Suspense fallback={<SystemStatusSkeleton />}>
          <SystemStatus />
        </Suspense>
      </section>

      <section className="mt-8 grid gap-2 rounded-xl border p-5 text-sm">
        <p className="font-medium">How a claim is checked</p>
        <ol className="list-decimal space-y-1 pl-5 text-muted-foreground">
          <li>Submit text, a URL, an article, an image, a PDF or video metadata.</li>
          <li>Atomic claims are extracted; the speaker is hidden from everything that judges them.</li>
          <li>Search providers find documents; only verbatim quotes become evidence.</li>
          <li>Evidence is ranked on authority, primary status, relevance, recency, directness, corroboration and quality.</li>
          <li>An assessor proposes a classification; an independent critic tries to disprove it.</li>
          <li>A human reviewer approves, rejects or asks for more research. Every step is audited.</li>
        </ol>
        <p>
          <Link href="/submit" className="underline underline-offset-2">Submit material</Link> ·{" "}
          <Link href="/claims" className="underline underline-offset-2">Browse claims</Link> ·{" "}
          <Link href="/review" className="underline underline-offset-2">Review queue</Link>
        </p>
      </section>
    </main>
  );
}
