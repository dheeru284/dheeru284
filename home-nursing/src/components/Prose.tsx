import type { ReactNode } from "react";

export function Prose({ title, draft, children }: { title: string; draft?: boolean; children: ReactNode }) {
  return (
    <article className="mx-auto max-w-3xl space-y-4 leading-relaxed text-ink-700 [&_h2]:mt-6 [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:text-ink-900 [&_li]:ml-5 [&_li]:list-disc">
      <h1 className="h1">{title}</h1>
      {draft && <p className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">Draft for legal review. This text is a placeholder and is not a final legal document.</p>}
      {children}
    </article>
  );
}
