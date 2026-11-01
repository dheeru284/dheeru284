import Link from "next/link";
import { Suspense } from "react";

import { ClassificationBadge } from "@/components/app/factcheck";
import { Loading, PageShell } from "@/components/app/page-shell";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { humanize, percent, shortDate } from "@/lib/format";
import { ApiError, api } from "@/lib/server-api";
import type { ReviewTask } from "@/lib/types";

async function Queue() {
  let tasks: ReviewTask[];
  try {
    tasks = await api<ReviewTask[]>("/review-tasks");
  } catch (err) {
    if (err instanceof ApiError && err.status === 403) {
      return <Alert>The review queue is for reviewers.</Alert>;
    }
    return <Alert tone="error">{err instanceof ApiError ? err.detail : "Could not load the queue."}</Alert>;
  }
  if (tasks.length === 0) return <p className="text-sm text-muted-foreground">Nothing is waiting for review.</p>;
  return (
    <Card>
      <CardContent>
        <ul className="divide-y">
          {tasks.map((t) => (
            <li key={t.id} className="grid gap-1 py-3">
              <Link href={`/claims/${t.claim_id}`} className="font-medium underline-offset-2 hover:underline">
                {t.claim_text}
              </Link>
              <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                <Badge variant={t.priority <= 1 ? "destructive" : t.priority === 2 ? "warning" : "outline"}>
                  P{t.priority} · {humanize(t.reason)}
                </Badge>
                <ClassificationBadge value={t.proposed_classification} />
                {t.proposed_confidence !== null && t.proposed_confidence > 0 && <span>{percent(t.proposed_confidence)}</span>}
                {t.submitted_by_me && <Badge variant="outline">your submission</Badge>}
                <span>· queued {shortDate(t.created_at)}</span>
              </div>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

export default function ReviewPage() {
  return (
    <PageShell
      title="Review queue"
      description="Escalations and stage failures first. Approving, rejecting or requesting more research is always a human decision."
    >
      <Suspense fallback={<Loading />}>
        <Queue />
      </Suspense>
    </PageShell>
  );
}
