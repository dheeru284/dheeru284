import Link from "next/link";
import { Suspense } from "react";

import { ClassificationBadge, ReviewBadge } from "@/components/app/factcheck";
import { AutoRefresh, TranscriptionForm } from "@/components/app/forms";
import { Loading, PageShell } from "@/components/app/page-shell";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { humanize, isInFlight, shortDate } from "@/lib/format";
import { ApiError, api } from "@/lib/server-api";
import type { SubmissionDetail } from "@/lib/types";

async function Detail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let data: SubmissionDetail;
  try {
    data = await api<SubmissionDetail>(`/submissions/${id}`);
  } catch (err) {
    return <Alert tone="error">{err instanceof ApiError ? err.detail : "Could not load submission."}</Alert>;
  }
  const { submission: s, claims, pipeline_jobs } = data;
  const inFlight = isInFlight(s.status, claims.map((c) => c.status));
  return (
    <div className="grid gap-4">
      <AutoRefresh active={inFlight} />
      <Card>
        <CardHeader>
          <CardTitle className="flex flex-wrap items-center gap-2">
            {humanize(s.submission_type)} submission <Badge variant="outline">{humanize(s.status)}</Badge>
          </CardTitle>
          <CardDescription className="break-words">
            {s.title ?? s.source_url ?? "Untitled"} · submitted {shortDate(s.created_at)}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-2 text-sm">
          <p>
            <span className="text-muted-foreground">Text obtained by:</span> {humanize(s.extraction_method)} (
            {s.extracted_chars.toLocaleString()} characters)
          </p>
          {s.extraction_notes && <p className="text-muted-foreground">{s.extraction_notes}</p>}
          <p className="text-xs text-muted-foreground">
            Stages: {pipeline_jobs.map((j) => `${humanize(j.stage)} ${j.status.toLowerCase()}`).join(" → ") || "queued"}
          </p>
        </CardContent>
      </Card>

      {s.status === "NEEDS_TRANSCRIPTION" && (
        <Card>
          <CardHeader>
            <CardTitle>Transcription needed</CardTitle>
            <CardDescription>
              No machine-readable text was found, and the system will not guess. Type the text so it can be checked.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <TranscriptionForm submissionId={s.id} />
          </CardContent>
        </Card>
      )}
      {s.status === "FAILED" && <Alert tone="error">Processing failed: {s.extraction_notes}</Alert>}
      {s.status === "NO_CLAIMS" && <Alert>No checkable claims were found in this material.</Alert>}

      {claims.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Extracted claims ({claims.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="divide-y">
              {claims.map((c) => (
                <li key={c.id} className="flex flex-wrap items-center justify-between gap-2 py-3">
                  <Link href={`/claims/${c.id}`} className="min-w-0 flex-1 underline-offset-2 hover:underline">
                    {c.text}
                  </Link>
                  <span className="flex flex-wrap gap-1.5">
                    <ClassificationBadge value={c.latest_classification} />
                    <ReviewBadge status={c.review_status === "NOT_READY" ? c.status : c.review_status} />
                  </span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default function SubmissionPage(props: PageProps<"/submissions/[id]">) {
  return (
    <PageShell title="Submission">
      <Suspense fallback={<Loading />}>
        <Detail params={props.params} />
      </Suspense>
    </PageShell>
  );
}
