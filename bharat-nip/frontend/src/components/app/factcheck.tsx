import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { classificationTone, humanize, percent, shortDate, shortHash } from "@/lib/format";
import type {
  AuditEvent,
  Claim,
  Classification,
  EvidenceItem,
  FactCheck,
  Provenance,
  SearchQuery,
} from "@/lib/types";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function ClassificationBadge({ value }: { value: Classification | null }) {
  if (!value) return <Badge variant="outline">Not assessed</Badge>;
  return <Badge variant={classificationTone(value)}>{humanize(value)}</Badge>;
}

export function ReviewBadge({ status }: { status: string }) {
  const tone =
    status === "APPROVED" ? "success" : status === "REJECTED" ? "destructive" : status === "PENDING_REVIEW" ? "warning" : "outline";
  return <Badge variant={tone}>{humanize(status)}</Badge>;
}

export function ProvenanceLine({ p, label }: { p: Provenance; label: string }) {
  if (!p) return <p className="text-xs text-muted-foreground">{label}: deterministic rule (no AI)</p>;
  return (
    <p className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
      {label}: {p.agent_name} · {p.provider}/{p.model} · prompt {p.prompt_id}@{p.prompt_version}{" "}
      <code title={p.prompt_sha256}>#{shortHash(p.prompt_sha256)}</code>
      {p.is_mock && <Badge variant="warning">MOCK</Badge>}
    </p>
  );
}

export function StructuredClaim({ claim }: { claim: Claim }) {
  const rows: [string, string | null][] = [
    ["Subject", claim.subject],
    ["Predicate", claim.predicate],
    ["Object", claim.object],
    ["Time", [claim.time_reference, claim.claim_date].filter(Boolean).join(" · ") || null],
    ["Location", claim.location],
    ["Type", `${humanize(claim.claim_type)}${claim.checkworthy ? "" : " (not check-worthy)"}`],
    ["Blinded text (what the assessor sees)", claim.normalized_text],
    [
      "Original source",
      [claim.original_source.submission_type, claim.original_source.url, claim.original_source.title]
        .filter(Boolean)
        .join(" · "),
    ],
    ["Extracted", shortDate(claim.extracted_at)],
  ];
  return (
    <Card>
      <CardHeader>
        <CardTitle>Extracted claim</CardTitle>
        <CardDescription>{claim.text}</CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[max-content_1fr]">
          {rows.map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="text-muted-foreground">{k}</dt>
              <dd className="break-words">{v || "—"}</dd>
            </div>
          ))}
          <dt className="text-muted-foreground">Entities</dt>
          <dd className="flex flex-wrap gap-1">
            {claim.entities.length === 0
              ? "—"
              : claim.entities.map((e) => (
                  <Badge key={`${e.name}-${e.role}`} variant="outline">
                    {e.name} · {humanize(e.role)}
                  </Badge>
                ))}
          </dd>
        </dl>
      </CardContent>
    </Card>
  );
}

function EvidenceCard({ item }: { item: EvidenceItem }) {
  const s = item.source;
  return (
    <li className="grid gap-2 rounded-lg border p-3">
      <blockquote className="border-l-2 pl-3 text-sm">“{item.quote}”</blockquote>
      <div className="flex flex-wrap items-center gap-1.5 text-xs">
        <Badge variant="outline">{humanize(item.directness)}</Badge>
        <Badge variant="outline">rank {item.rank_score.toFixed(2)}</Badge>
        <Badge variant="outline">relevance {item.relevance.toFixed(2)}</Badge>
        {s.is_primary && <Badge variant="secondary">primary source</Badge>}
        <Badge variant="outline">{humanize(s.authority_level)}</Badge>
        {item.cited && <Badge>cited</Badge>}
      </div>
      <p className="text-xs break-words text-muted-foreground">
        {s.url ? (
          <a href={s.url} className="underline underline-offset-2" rel="noreferrer noopener" target="_blank">
            {s.title}
          </a>
        ) : (
          s.title
        )}{" "}
        · {s.publisher ?? "unknown publisher"} · {humanize(s.source_type)} · published {shortDate(s.published_at)} ·
        retrieved {shortDate(s.retrieved_at)} · <code title={s.content_sha256}>sha256 {shortHash(s.content_sha256)}</code>
      </p>
    </li>
  );
}

export function EvidenceSection({ title, items, empty }: { title: string; items: EvidenceItem[]; empty: string }) {
  return (
    <section className="grid gap-2">
      <h3 className="text-sm font-semibold">
        {title} ({items.length})
      </h3>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{empty}</p>
      ) : (
        <ul className="grid gap-2">
          {items.map((e) => (
            <EvidenceCard key={e.evidence_id} item={e} />
          ))}
        </ul>
      )}
    </section>
  );
}

export function FactCheckResult({ fc }: { fc: FactCheck }) {
  const noDetermination = fc.confidence === 0;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          Fact-check result <ClassificationBadge value={fc.classification} />
          <ReviewBadge status={fc.review_status} />
          {fc.final_classification && fc.final_classification !== fc.classification && (
            <span className="text-sm font-normal">
              reviewer changed to <ClassificationBadge value={fc.final_classification} />
            </span>
          )}
        </CardTitle>
        <CardDescription>
          Revision {fc.revision} · {fc.produced_by === "RULE" ? "decided by rule" : "proposed by the assessor agent"} ·
          confidence {noDetermination ? "0 (no evidential determination)" : percent(fc.confidence)}
          {fc.confidence_raw !== null && fc.confidence_raw !== fc.confidence && ` (agent proposed ${percent(fc.confidence_raw)})`}
        </CardDescription>
      </CardHeader>
      <CardContent className="grid gap-5">
        {fc.review_decision && (
          <div className="rounded-md border bg-muted px-3 py-2 text-sm">
            <p className="font-medium">
              Reviewer decision: {humanize(fc.review_decision.decision)}
              {fc.review_decision.final_classification && ` as ${humanize(fc.review_decision.final_classification)}`} ·{" "}
              {shortDate(fc.review_decision.decided_at)}
            </p>
            {fc.review_decision.notes && <p className="text-muted-foreground">{fc.review_decision.notes}</p>}
          </div>
        )}
        <div className="grid gap-1">
          <p className="font-medium">{fc.summary}</p>
          <p className="text-sm whitespace-pre-line text-muted-foreground">{fc.reasoning}</p>
        </div>
        {fc.guardrails.length > 0 && (
          <div className="grid gap-1">
            <h3 className="text-sm font-semibold">Guardrails applied</h3>
            <ul className="list-disc pl-5 text-sm text-muted-foreground">
              {fc.guardrails.map((g) => (
                <li key={g.rule}>
                  <code>{g.rule}</code>: {g.detail}
                </li>
              ))}
            </ul>
          </div>
        )}
        <EvidenceSection title="Supporting evidence" items={fc.supporting_evidence} empty="None found." />
        <EvidenceSection title="Contradicting evidence" items={fc.contradicting_evidence} empty="None found." />
        {fc.context_evidence.length > 0 && (
          <EvidenceSection title="Context and mixed evidence" items={fc.context_evidence} empty="" />
        )}
        <div className="grid gap-1">
          <h3 className="text-sm font-semibold">Missing information</h3>
          {fc.missing_information.length === 0 ? (
            <p className="text-sm text-muted-foreground">None noted.</p>
          ) : (
            <ul className="list-disc pl-5 text-sm">
              {fc.missing_information.map((m) => (
                <li key={m}>{m}</li>
              ))}
            </ul>
          )}
        </div>
        <p className="text-sm">
          <span className="text-muted-foreground">Recommended action:</span> {humanize(fc.recommended_action)}
        </p>
        <ProvenanceLine p={fc.provenance} label="Assessment" />
      </CardContent>
    </Card>
  );
}

export function CriticPanel({ critic }: { critic: NonNullable<FactCheck["critic"]> }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          Independent critic
          <Badge variant={critic.outcome === "PASS" ? "success" : critic.outcome === "REVISE" ? "warning" : "destructive"}>
            {critic.outcome}
          </Badge>
          {critic.outcome_overridden && (
            <span className="text-xs font-normal text-muted-foreground">
              critic said {critic.agent_outcome}; overridden by a high-severity automated finding
            </span>
          )}
        </CardTitle>
        <CardDescription>Tries to disprove the assessment. Counter-argument: {critic.counter_argument}</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <ul className="grid gap-1.5 text-sm">
          {critic.checks.map((c) => (
            <li key={c.check} className="flex flex-wrap items-start gap-2">
              <Badge variant={c.passed ? "success" : "destructive"}>{c.passed ? "pass" : "fail"}</Badge>
              <span className="font-medium">{humanize(c.check)}</span>
              <span className="text-muted-foreground">{c.detail}</span>
            </li>
          ))}
        </ul>
        {critic.deterministic_findings.length > 0 && (
          <div className="grid gap-1">
            <h3 className="text-sm font-semibold">Automated findings</h3>
            <ul className="grid gap-1 text-sm">
              {critic.deterministic_findings.map((f, i) => (
                <li key={`${f.check}-${i}`} className="flex flex-wrap gap-2">
                  <Badge variant={f.severity === "HIGH" ? "destructive" : "warning"}>{f.severity}</Badge>
                  {humanize(f.check)}: {f.detail}
                </li>
              ))}
            </ul>
          </div>
        )}
        {critic.suggested_classification && (
          <p className="text-sm">
            Critic would classify as <ClassificationBadge value={critic.suggested_classification} />
          </p>
        )}
        <ProvenanceLine p={critic.provenance} label="Critic" />
      </CardContent>
    </Card>
  );
}

export function SearchesPanel({ searches }: { searches: SearchQuery[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Searches</CardTitle>
        <CardDescription>Every query sent to a search provider for this claim, and what came back.</CardDescription>
      </CardHeader>
      <CardContent>
        {searches.length === 0 ? (
          <p className="text-sm text-muted-foreground">No searches (non-checkable claim, or not researched yet).</p>
        ) : (
          <ul className="grid gap-3 text-sm">
            {searches.map((s) => (
              <li key={s.id} className="grid gap-1">
                <p>
                  <Badge variant={s.provider === "mock" ? "warning" : "outline"}>{s.provider}</Badge>{" "}
                  <code className="break-words">{s.query_text}</code> · {s.result_count} result(s)
                  {s.error && <span className="text-destructive"> · {s.error}</span>}
                </p>
                <ul className="pl-4 text-xs text-muted-foreground">
                  {s.results.map((r) => (
                    <li key={r.rank} className="break-words">
                      {r.rank}. {r.title} · {humanize(r.fetch_status)}
                      {r.fetch_error && ` (${r.fetch_error})`}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

export function AuditTrail({ events }: { events: AuditEvent[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Audit trail</CardTitle>
        <CardDescription>Append-only and hash-chained. Each entry records who or what acted.</CardDescription>
      </CardHeader>
      <CardContent>
        <ol className="grid gap-1.5 text-xs">
          {events.map((e) => (
            <li key={e.seq} className="grid gap-x-3 sm:grid-cols-[3rem_15rem_1fr]">
              <span className="text-muted-foreground">#{e.seq}</span>
              <code className="break-all">{e.action}</code>
              <span className="break-words text-muted-foreground">
                {e.actor_type.toLowerCase()} {UUID_RE.test(e.actor_id) ? shortHash(e.actor_id, 8) : e.actor_id} ·{" "}
                {new Date(e.occurred_at).toISOString().replace("T", " ").slice(0, 19)} · hash {shortHash(e.hash, 8)}
              </span>
            </li>
          ))}
        </ol>
      </CardContent>
    </Card>
  );
}
