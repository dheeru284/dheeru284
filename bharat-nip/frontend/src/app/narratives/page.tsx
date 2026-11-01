import Link from "next/link";
import { Suspense } from "react";

import { AnalyzeButton } from "@/components/app/narrative-forms";
import { Loading, PageShell } from "@/components/app/page-shell";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { humanize, percent, shortDate } from "@/lib/format";
import { type Dashboard, NARRATIVE_STATUSES, RECOMMENDATIONS, evidenceTone, recommendationTone } from "@/lib/narratives";
import { ApiError, api } from "@/lib/server-api";

async function Content({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  const sp = await searchParams;
  const rec = typeof sp.recommendation === "string" ? sp.recommendation : "";
  const query = rec ? `?recommendation=${encodeURIComponent(rec)}` : "";
  let data: Dashboard;
  try {
    data = await api<Dashboard>(`/narratives${query}`);
  } catch (err) {
    if (err instanceof ApiError && err.status === 403) return <Alert>Narrative intelligence is for analysts and above.</Alert>;
    return <Alert tone="error">{err instanceof ApiError ? err.detail : "Could not load narratives."}</Alert>;
  }
  return (
    <div className="grid gap-5">
      <div className="grid gap-3 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>By recommendation</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            <Link href="/narratives" className={`rounded-md border px-2 py-1 text-xs ${rec ? "" : "border-primary bg-muted"}`}>
              All
            </Link>
            {RECOMMENDATIONS.map((r) => (
              <Link
                key={r}
                href={`/narratives?recommendation=${r}`}
                className={`rounded-md border px-2 py-1 text-xs ${rec === r ? "border-primary bg-muted" : ""}`}
              >
                {humanize(r)} · {data.counts.by_recommendation[r] ?? 0}
              </Link>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>By status</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2 text-xs">
            {NARRATIVE_STATUSES.map((s) => (
              <span key={s} className="rounded-md border px-2 py-1">
                {humanize(s)} · {data.counts.by_status[s] ?? 0}
              </span>
            ))}
          </CardContent>
        </Card>
      </div>

      {data.emerging_topics.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Emerging topics</CardTitle>
            <CardDescription>At least 3 claims in the last 7 days, and at least twice the usual weekly volume plus one.</CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="grid gap-1.5 text-sm">
              {data.emerging_topics.map((t) => (
                <li key={t.id} className="flex flex-wrap items-center gap-2">
                  <Badge variant="warning">emerging</Badge>
                  <span className="font-medium">{t.label}</span>
                  <span className="text-muted-foreground">
                    {t.recent_count} this week vs {t.baseline_weekly.toFixed(1)}/week before
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Narratives ({data.items.length})</CardTitle>
          <CardDescription>Sorted by recommendation priority, then momentum. Archived narratives are hidden.</CardDescription>
        </CardHeader>
        <CardContent>
          {data.items.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No narratives yet. A narrative appears when similar claims arrive from at least two submissions.
            </p>
          ) : (
            <ul className="divide-y">
              {data.items.map((n) => {
                const m = n.metrics;
                return (
                  <li key={n.id} className="grid gap-1.5 py-3">
                    <Link href={`/narratives/${n.id}`} className="font-medium underline-offset-2 hover:underline">
                      {n.title}
                    </Link>
                    <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                      {m && <Badge variant={recommendationTone(m.recommendation)}>{humanize(m.recommendation)}</Badge>}
                      <Badge variant="outline">{humanize(n.status)}</Badge>
                      {m && <Badge variant={evidenceTone(m.evidence_status)}>{humanize(m.evidence_status)}</Badge>}
                      {m?.recurring && <Badge variant="secondary">recurring</Badge>}
                      {m?.details.reactivated && <Badge variant="warning">reactivated</Badge>}
                      {m && (
                        <span>
                          {m.claim_count} claims · momentum {percent(m.momentum)} · relevance {percent(m.public_interest)}
                        </span>
                      )}
                      <span>· last seen {shortDate(n.last_seen_at)}</span>
                      {n.topic && <span>· {n.topic.label}</span>}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function NarrativesPage(props: PageProps<"/narratives">) {
  return (
    <PageShell
      title="Narrative intelligence"
      description={
        <>
          Narratives are recurring claims grouped from the verified evidence layer. Only aggregate, public information is
          used, and nothing here profiles individual people. <Link href="/narratives/graph" className="underline">Open the graph</Link>.
        </>
      }
    >
      <AnalyzeButton />
      <Suspense fallback={<Loading />}>
        <Content searchParams={props.searchParams} />
      </Suspense>
    </PageShell>
  );
}
