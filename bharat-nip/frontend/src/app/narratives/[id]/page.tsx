import Link from "next/link";
import { Suspense } from "react";

import { MetricsChart } from "@/components/app/metrics-chart";
import { HarmForm, ObservationForm, ResponseForm, StatusForm } from "@/components/app/narrative-forms";
import { Loading, PageShell } from "@/components/app/page-shell";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { classificationTone, humanize, percent, shortDate } from "@/lib/format";
import {
  type ClaimHistoryItem,
  type NarrativeDetail,
  type NarrativeMetrics,
  type TimelineEvent,
  burstCount,
  evidenceTone,
  recommendationTone,
} from "@/lib/narratives";
import { ApiError, api } from "@/lib/server-api";
import type { Classification } from "@/lib/types";

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="grid gap-0.5 rounded-lg border p-3">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-lg font-semibold">{value}</span>
      {hint && <span className="text-xs text-muted-foreground">{hint}</span>}
    </div>
  );
}

function Recommendation({ m }: { m: NarrativeMetrics }) {
  const r = m.details.recommendation;
  return (
    <Card className="border-primary">
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          Recommendation <Badge variant={recommendationTone(m.recommendation)}>{humanize(m.recommendation)}</Badge>
          <span className="text-sm font-normal text-muted-foreground">suggested status: {humanize(m.suggested_status)}</span>
        </CardTitle>
        <CardDescription>
          {r.rationale} (rule {r.rule}, {r.version}). A recommendation is advice to people; nothing is published automatically.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-3">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          <Stat label="Evidence status" value={humanize(m.evidence_status)} hint={`strength ${percent(m.evidence_strength)}`} />
          <Stat label="Public relevance" value={percent(m.public_interest)} hint={m.details.levels.public_relevance} />
          <Stat label="Momentum" value={percent(m.momentum)} hint={m.details.levels.momentum} />
          <Stat label="Potential harm" value={humanize(m.details.harm.severity)} hint={humanize(m.details.harm.category)} />
          <Stat label="Uncertainty" value={percent(m.uncertainty)} />
          <Stat label="Response coverage" value={percent(m.coverage)} hint={m.details.coverage.stale ? "stale: new activity since" : undefined} />
        </div>
        <details className="text-xs text-muted-foreground">
          <summary className="cursor-pointer">Decision trace</summary>
          <ol className="mt-1 list-decimal pl-5">
            {r.trace.map((t) => (
              <li key={t}>
                <code>{t}</code>
              </li>
            ))}
          </ol>
        </details>
      </CardContent>
    </Card>
  );
}

function ClaimHistory({ items }: { items: ClaimHistoryItem[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Claim history</CardTitle>
        <CardDescription>
          {items.length} claims in {burstCount(items)} burst(s); a new burst starts after a gap of more than 7 days. Speakers are
          not shown.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ol className="grid gap-2 text-sm">
          {items.map((c) => (
            <li key={c.claim_id} className="grid gap-1 border-l-2 pl-3">
              <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                <span>{shortDate(c.seen_at)}</span>
                <Badge variant="outline">burst {c.burst}</Badge>
                {c.approved_classification ? (
                  <Badge variant={classificationTone(c.approved_classification as Classification)}>
                    approved: {humanize(c.approved_classification)}
                  </Badge>
                ) : (
                  <Badge variant="outline">{humanize(c.review_status)}</Badge>
                )}
                <span>{c.origin ?? "origin unknown"}</span>
                <span>· {humanize(c.submission_type)}</span>
                {c.added_by === "USER" && <Badge variant="secondary">added by analyst</Badge>}
              </div>
              <Link href={`/claims/${c.claim_id}`} className="underline-offset-2 hover:underline">
                {c.text}
              </Link>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  );
}

function EvidenceTimeline({ events }: { events: TimelineEvent[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Evidence timeline</CardTitle>
        <CardDescription>Evidence by its publication date (or retrieval date if unknown), plus human review decisions.</CardDescription>
      </CardHeader>
      <CardContent>
        {events.length === 0 ? (
          <p className="text-sm text-muted-foreground">No evidence or decisions yet.</p>
        ) : (
          <ol className="grid gap-3 text-sm">
            {events.map((e) => (
              <li key={e.kind === "EVIDENCE" ? e.evidence_id : `${e.claim_id}-${e.at}`} className="grid gap-1 border-l-2 pl-3">
                <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                  <span>{shortDate(e.at)}</span>
                  {e.kind === "EVIDENCE" ? (
                    <>
                      <Badge variant={e.stance === "REFUTES" ? "destructive" : e.stance === "SUPPORTS" ? "success" : "outline"}>
                        {humanize(e.stance)}
                      </Badge>
                      <span>
                        {e.source.publisher ?? "unknown publisher"} · {humanize(e.source.source_type)}
                        {e.source.is_primary ? " · primary" : ""}
                        {e.date_basis === "retrieved" ? " · date = retrieved" : ""}
                        {e.claim_ids.length > 1 ? ` · supports ${e.claim_ids.length} claims` : ""}
                      </span>
                    </>
                  ) : (
                    <Badge variant="secondary">
                      review: {humanize(e.decision)}
                      {e.final_classification ? ` as ${humanize(e.final_classification)}` : ""}
                    </Badge>
                  )}
                </div>
                {e.kind === "EVIDENCE" && (
                  <p>
                    “{e.quote}”{" "}
                    {e.source.url ? (
                      <a href={e.source.url} target="_blank" rel="noreferrer noopener" className="text-xs underline">
                        {e.source.title}
                      </a>
                    ) : (
                      <span className="text-xs text-muted-foreground">{e.source.title}</span>
                    )}
                  </p>
                )}
              </li>
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}

async function Detail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let n: NarrativeDetail, history: ClaimHistoryItem[], timeline: TimelineEvent[], series: NarrativeMetrics[];
  try {
    [n, history, timeline, series] = await Promise.all([
      api<NarrativeDetail>(`/narratives/${id}`),
      api<ClaimHistoryItem[]>(`/narratives/${id}/claims`),
      api<TimelineEvent[]>(`/narratives/${id}/evidence-timeline`),
      api<NarrativeMetrics[]>(`/narratives/${id}/metrics`),
    ]);
  } catch (err) {
    return <Alert tone="error">{err instanceof ApiError ? err.detail : "Could not load narrative."}</Alert>;
  }
  const m = n.metrics;
  return (
    <div className="grid gap-4">
      <div className="grid gap-1">
        <h2 className="text-xl font-semibold">{n.title}</h2>
        <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
          <Badge variant="outline">{humanize(n.status)}</Badge>
          {m && <Badge variant={evidenceTone(m.evidence_status)}>{humanize(m.evidence_status)}</Badge>}
          {m?.recurring && <Badge variant="secondary">recurring</Badge>}
          {m?.details.reactivated && <Badge variant="warning">new activity after {humanize(n.status)}</Badge>}
          <span>
            {humanize(n.origin)} · first seen {shortDate(n.first_seen_at)} · last seen {shortDate(n.last_seen_at)}
          </span>
          {n.topic && <span>· topic {n.topic.label}</span>}
        </div>
        {n.summary && <p className="text-sm">{n.summary}</p>}
      </div>

      {m ? <Recommendation m={m} /> : <Alert>Metrics will appear after the next analysis run.</Alert>}

      {m && (
        <Card>
          <CardHeader>
            <CardTitle>Activity and public interest</CardTitle>
            <CardDescription>Aggregate indicators only.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Stat label="Claims" value={String(m.claim_count)} hint={`${m.details.bursts} burst(s)`} />
              <Stat label="Velocity (7 days)" value={`${m.rate_7d.toFixed(2)}/day`} hint={`${m.details.velocity.count_7d} this week`} />
              <Stat label="Acceleration" value={m.acceleration >= 0 ? `+${m.acceleration}` : String(m.acceleration)} hint="vs previous week" />
              <Stat
                label="Origins / channels"
                value={`${m.details.public_interest_indicators.distinct_origins} / ${m.details.public_interest_indicators.channels}`}
                hint={`reach ${m.details.public_interest_indicators.reach.toLocaleString()}`}
              />
            </div>
            <MetricsChart series={series} />
            {m.details.harm.signals.length > 0 && (
              <Alert tone="warning">
                Possible harm signals (keywords, for an analyst to assess; they never set severity):{" "}
                {m.details.harm.signals.map((s) => `${humanize(s.category)} (${s.keywords})`).join("; ")}
              </Alert>
            )}
          </CardContent>
        </Card>
      )}

      <ClaimHistory items={history} />
      <EvidenceTimeline events={timeline} />

      {n.related.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Related narratives</CardTitle>
            <CardDescription>
              <Link href="/narratives/graph" className="underline">
                View the graph
              </Link>
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="grid gap-1.5 text-sm">
              {n.related.map((r) => (
                <li key={`${r.narrative_id}-${r.type}`} className="flex flex-wrap items-center gap-2">
                  <Badge variant={r.type === "CONTRADICTS" ? "destructive" : "outline"}>{humanize(r.type)}</Badge>
                  <Link href={`/narratives/${r.narrative_id}`} className="underline-offset-2 hover:underline">
                    {r.title}
                  </Link>
                  <span className="text-xs text-muted-foreground">weight {r.weight.toFixed(2)}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Status</CardTitle>
            <CardDescription>
              Current: {humanize(n.status)}
              {n.status_note ? ` (${n.status_note})` : ""}. Only people change status.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <StatusForm narrativeId={n.id} allowed={n.allowed_status_transitions} suggested={m?.suggested_status ?? null} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Potential harm</CardTitle>
            <CardDescription>
              {humanize(n.harm_severity)} · {humanize(n.harm_category)}
              {n.harm_rationale ? `: ${n.harm_rationale}` : ""}. Assess real-world consequences, never political effect.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <HarmForm narrativeId={n.id} category={n.harm_category} severity={n.harm_severity} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Public observations ({n.observations.length})</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3">
            {n.observations.length > 0 && (
              <ul className="grid gap-1 text-xs text-muted-foreground">
                {n.observations.map((o) => (
                  <li key={o.id}>
                    {shortDate(o.observed_at)} · {o.channel} · {humanize(o.metric)} {o.value.toLocaleString()}
                  </li>
                ))}
              </ul>
            )}
            <ObservationForm narrativeId={n.id} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Existing responses ({n.responses.length})</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3">
            {n.responses.length > 0 && (
              <ul className="grid gap-1 text-xs text-muted-foreground">
                {n.responses.map((r) => (
                  <li key={r.id}>
                    {shortDate(r.published_at)} · {humanize(r.response_type)} · {r.title}
                  </li>
                ))}
              </ul>
            )}
            <ResponseForm narrativeId={n.id} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default function NarrativePage(props: PageProps<"/narratives/[id]">) {
  return (
    <PageShell title="Narrative">
      <Suspense fallback={<Loading />}>
        <Detail params={props.params} />
      </Suspense>
    </PageShell>
  );
}
