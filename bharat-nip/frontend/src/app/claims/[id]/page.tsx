import Link from "next/link";
import { Suspense } from "react";

import {
  AuditTrail,
  ClassificationBadge,
  CriticPanel,
  FactCheckResult,
  ReviewBadge,
  SearchesPanel,
  StructuredClaim,
} from "@/components/app/factcheck";
import { AutoRefresh, RerunResearchButton, ReviewForm } from "@/components/app/forms";
import { Loading, PageShell } from "@/components/app/page-shell";
import { Alert } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { humanize, isInFlight, percent } from "@/lib/format";
import { ApiError, api } from "@/lib/server-api";
import type { Assessment, AuditEvent, ClaimDetail, FactCheck, ReviewTask, SearchQuery, User } from "@/lib/types";

async function optional<T>(p: Promise<T>): Promise<T | null> {
  try {
    return await p;
  } catch (err) {
    if (err instanceof ApiError && (err.status === 403 || err.status === 404)) return null;
    throw err;
  }
}

async function Detail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let detail: ClaimDetail;
  let me: User;
  try {
    [detail, me] = await Promise.all([api<ClaimDetail>(`/claims/${id}`), api<User>("/auth/me")]);
  } catch (err) {
    return <Alert tone="error">{err instanceof ApiError ? err.detail : "Could not load claim."}</Alert>;
  }
  const isAnalyst = me.role !== "SUBMITTER";
  const isReviewer = me.role === "REVIEWER" || me.role === "ADMIN";
  const { claim } = detail;
  const [fc, assessments, searches, audit, task] = await Promise.all([
    optional(api<FactCheck>(`/claims/${id}/fact-check`)),
    optional(api<Assessment[]>(`/claims/${id}/assessments`)),
    isAnalyst ? optional(api<SearchQuery[]>(`/claims/${id}/searches`)) : null,
    isAnalyst ? optional(api<AuditEvent[]>(`/claims/${id}/audit`)) : null,
    isReviewer && detail.open_review_task_id
      ? optional(api<ReviewTask>(`/review-tasks/${detail.open_review_task_id}`))
      : null,
  ]);

  return (
    <div className="grid gap-4">
      <AutoRefresh active={isInFlight("PROCESSED", [claim.status])} />
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <ReviewBadge status={claim.review_status === "NOT_READY" ? claim.status : claim.review_status} />
        <span className="text-muted-foreground">Pipeline status: {humanize(claim.status)}</span>
        <Link href={`/submissions/${claim.submission_id}`} className="ml-auto underline underline-offset-2">
          View submission
        </Link>
      </div>

      {task && (
        <Card className="border-primary">
          <CardHeader>
            <CardTitle>Human review</CardTitle>
            <CardDescription>
              Reason: {humanize(task.reason)}
              {task.reason_detail && ` (${task.reason_detail})`}. No agent can approve its own work: a person decides.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {task.submitted_by_me ? (
              <Alert tone="warning">You submitted this material, so another reviewer must decide (four-eyes rule).</Alert>
            ) : (
              <ReviewForm taskId={task.id} proposed={task.proposed_classification} hasAssessment={!!task.assessment_id} />
            )}
          </CardContent>
        </Card>
      )}
      {claim.status === "NEEDS_MORE_RESEARCH" && isAnalyst && (
        <Card>
          <CardHeader>
            <CardTitle>More research requested</CardTitle>
            <CardDescription>
              Add sources to the corpus (POST /api/v1/sources) or configure web search, then re-run.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <RerunResearchButton claimId={claim.id} />
          </CardContent>
        </Card>
      )}

      {fc ? (
        <FactCheckResult fc={fc} />
      ) : (
        <Alert>
          {isAnalyst
            ? "No assessment yet."
            : "The result will appear here once a reviewer has approved it."}
        </Alert>
      )}
      {fc?.critic && <CriticPanel critic={fc.critic} />}
      <StructuredClaim claim={claim} />

      {assessments && assessments.length > 1 && (
        <Card>
          <CardHeader>
            <CardTitle>Revision history</CardTitle>
            <CardDescription>Each revision is kept; superseded ones are never deleted.</CardDescription>
          </CardHeader>
          <CardContent>
            <ol className="grid gap-2 text-sm">
              {assessments.map((a) => (
                <li key={a.id} className="flex flex-wrap items-center gap-2">
                  <span className="text-muted-foreground">Rev {a.revision}</span>
                  <ClassificationBadge value={a.classification} />
                  <span>{a.confidence > 0 ? percent(a.confidence) : "no determination"}</span>
                  <span className="text-muted-foreground">
                    {humanize(a.status)}
                    {a.critiques.map((c) => ` · critic ${c.outcome}`).join("")}
                  </span>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      )}
      {searches && <SearchesPanel searches={searches} />}
      {detail.pipeline_jobs.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Pipeline stages</CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="grid gap-1 text-sm">
              {detail.pipeline_jobs.map((j) => (
                <li key={j.id} className="flex flex-wrap gap-2">
                  <span className="w-28">{humanize(j.stage)}</span>
                  <span className={j.status === "FAILED" ? "text-destructive" : "text-muted-foreground"}>
                    {humanize(j.status)}
                    {j.attempt > 1 && ` (attempt ${j.attempt})`}
                    {j.error && `: ${j.error}`}
                  </span>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      )}
      {audit && <AuditTrail events={audit} />}
    </div>
  );
}

export default function ClaimPage(props: PageProps<"/claims/[id]">) {
  return (
    <PageShell title="Claim">
      <Suspense fallback={<Loading />}>
        <Detail params={props.params} />
      </Suspense>
    </PageShell>
  );
}
