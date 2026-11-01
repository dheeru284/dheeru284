import Link from "next/link";
import { Suspense } from "react";

import { ClassificationBadge, ReviewBadge } from "@/components/app/factcheck";
import { Loading, PageShell } from "@/components/app/page-shell";
import { Alert } from "@/components/ui/alert";
import { Card, CardContent } from "@/components/ui/card";
import { humanize, percent, shortDate } from "@/lib/format";
import { ApiError, api } from "@/lib/server-api";
import type { Claim, Page } from "@/lib/types";

const FILTERS = ["ALL", "PENDING_REVIEW", "APPROVED", "NEEDS_MORE_RESEARCH", "REJECTED", "NOT_READY"];

async function ClaimList({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const sp = await searchParams;
  const filter = typeof sp.review_status === "string" ? sp.review_status : "ALL";
  const query = filter === "ALL" ? "" : `?review_status=${encodeURIComponent(filter)}`;
  let page: Page<Claim>;
  try {
    page = await api<Page<Claim>>(`/claims${query}`);
  } catch (err) {
    return <Alert tone="error">{err instanceof ApiError ? err.detail : "Could not load claims."}</Alert>;
  }
  return (
    <div className="grid gap-4">
      <nav className="flex flex-wrap gap-2 text-sm" aria-label="Filter by review status">
        {FILTERS.map((f) => (
          <Link
            key={f}
            href={f === "ALL" ? "/claims" : `/claims?review_status=${f}`}
            className={`rounded-md border px-2.5 py-1 ${f === filter ? "border-primary bg-muted" : ""}`}
          >
            {humanize(f)}
          </Link>
        ))}
      </nav>
      <Card>
        <CardContent>
          {page.items.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No claims here yet. <Link href="/submit" className="underline">Submit something</Link>.
            </p>
          ) : (
            <ul className="divide-y">
              {page.items.map((c) => (
                <li key={c.id} className="grid gap-1 py-3">
                  <Link href={`/claims/${c.id}`} className="font-medium underline-offset-2 hover:underline">
                    {c.text}
                  </Link>
                  <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                    <ClassificationBadge value={c.latest_classification} />
                    {c.latest_confidence !== null && c.latest_confidence > 0 && <span>{percent(c.latest_confidence)}</span>}
                    <ReviewBadge status={c.review_status === "NOT_READY" ? c.status : c.review_status} />
                    <span>{humanize(c.claim_type)}</span>
                    <span>· extracted {shortDate(c.extracted_at)}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function ClaimsPage(props: PageProps<"/claims">) {
  return (
    <PageShell title="Claims" description="Every extracted claim, its latest classification and review status.">
      <Suspense fallback={<Loading />}>
        <ClaimList searchParams={props.searchParams} />
      </Suspense>
    </PageShell>
  );
}
