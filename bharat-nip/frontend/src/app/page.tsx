import { Suspense } from "react";

import { SystemStatus, SystemStatusSkeleton } from "@/components/system-status";

export default function Home() {
  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-10 sm:px-6">
      <header className="mb-8 grid gap-2">
        <p className="text-sm font-medium text-muted-foreground">Phase 0 · Foundation</p>
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

      <section className="mt-8 rounded-xl border border-dashed p-5 text-sm text-muted-foreground">
        <p className="font-medium text-foreground">Not built yet</p>
        <p className="mt-1">
          Claim submission, evidence review and the human review queue arrive in Phases 1–2 (see
          ROADMAP.md). This page only shows what the backend actually reports today.
        </p>
      </section>
    </main>
  );
}
