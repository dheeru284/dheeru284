import Link from "next/link";
import { Suspense } from "react";

import { AutoRefresh } from "@/components/app/forms";
import { TaskActions } from "@/components/app/org-forms";
import { Loading, PageShell } from "@/components/app/page-shell";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { humanize } from "@/lib/format";
import { LIFECYCLE, type TaskDetail, lifecycleReached, taskTone } from "@/lib/org";
import { ApiError, api } from "@/lib/server-api";
import type { User } from "@/lib/types";

type Workflows = ({ workflow: string; steps: { key: string; revisable: boolean }[] } | { supported_languages: unknown })[];

function Json({ value }: { value: unknown }) {
  return (
    <pre className="max-h-64 overflow-auto rounded bg-muted p-2 text-[11px] leading-snug whitespace-pre-wrap break-words">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}

async function Detail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let t: TaskDetail, me: User, workflows: Workflows;
  try {
    [t, me, workflows] = await Promise.all([api<TaskDetail>(`/org/tasks/${id}`), api<User>("/auth/me"), api<Workflows>("/org/workflows")]);
  } catch (err) {
    return <Alert tone="error">{err instanceof ApiError ? err.detail : "Could not load the task."}</Alert>;
  }
  const reached = lifecycleReached(t.executions);
  const wf = workflows.find((w) => "workflow" in w && w.workflow === t.workflow) as { steps: { key: string; revisable: boolean }[] } | undefined;
  const revisable = (wf?.steps ?? []).filter((s) => s.revisable && t.steps.some((x) => x.step_key === s.key && x.status !== "SKIPPED")).map((s) => s.key);
  const stepName = Object.fromEntries(t.steps.map((s) => [s.step_key, s.agent_name]));
  return (
    <div className="grid gap-4">
      <AutoRefresh active={t.status === "PENDING" || t.status === "IN_PROGRESS"} />
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-xl font-semibold">{t.title}</h2>
        <Badge variant={taskTone(t.status)}>
          {humanize(t.status)}
        </Badge>
        <span className="text-xs text-muted-foreground">
          {humanize(t.workflow)} · approval by {t.approval_level === "HUMAN" ? "a human reviewer" : "the Chief Intelligence Agent"} ·{" "}
          {t.executions_used}/{t.max_executions} executions · {t.human_revisions} human revision(s)
        </span>
      </div>
      {t.escalation_reason && <Alert tone="error">Escalated: {t.escalation_reason}</Alert>}

      <Card>
        <CardHeader>
          <CardTitle>Lifecycle</CardTitle>
          <CardDescription>Task → delegation → execution → review → revision → approval → completion.</CardDescription>
        </CardHeader>
        <CardContent>
          <ol className="flex flex-wrap gap-2 text-xs">
            {LIFECYCLE.map((k) => (
              <li key={k} className={`rounded-md border px-2 py-1 ${reached[k] ? "border-primary bg-muted font-medium" : "text-muted-foreground"}`}>
                {humanize(k)} {reached[k] ? `×${reached[k]}` : ""}
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Steps</CardTitle>
          <CardDescription>Fixed by the workflow template. Agents cannot add, skip or reorder steps.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3">
          {t.steps.map((s) => (
            <div key={s.step_key} className="grid gap-1.5 rounded-lg border p-3">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="font-medium">
                  {s.seq + 1}. {s.agent_name}
                </span>
                <Badge variant={s.status === "DONE" ? "success" : s.status === "ESCALATED" ? "destructive" : "outline"}>{humanize(s.status)}</Badge>
                <span className="text-xs text-muted-foreground">
                  step {s.step_key} · delegated by {humanize(s.delegated_by)} · reviewed by {s.reviewer.toLowerCase()} · iterations{" "}
                  {s.iterations}/{s.max_iterations}
                  {s.retries ? ` · retried ${s.retries}` : ""}
                </span>
              </div>
              {s.escalation && (
                <p className="text-xs text-destructive">
                  {s.escalation.condition} → {s.escalation.target.toLowerCase()}: {s.escalation.detail}
                </p>
              )}
              {s.feedback.length > 0 && (
                <ul className="list-disc pl-5 text-xs text-muted-foreground">
                  {s.feedback.map((f, i) => (
                    <li key={i}>
                      {f.from} feedback: {f.summary}
                    </li>
                  ))}
                </ul>
              )}
              {s.output && (
                <details className="text-xs">
                  <summary className="cursor-pointer text-muted-foreground">Output</summary>
                  <Json value={s.output} />
                </details>
              )}
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Decision</CardTitle>
          <CardDescription>Only people approve public-facing work; nothing is published by the system.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3">
          {t.approvals.length > 0 && (
            <ul className="grid gap-1 text-xs">
              {t.approvals.map((a, i) => (
                <li key={i}>
                  {a.approver_type === "HUMAN" ? "Human reviewer" : humanize(a.approver)}: {humanize(a.decision)}
                  {a.target_step ? ` (${a.target_step})` : ""}
                  {a.notes ? `: ${a.notes}` : ""}
                </li>
              ))}
            </ul>
          )}
          <TaskActions
            taskId={t.id}
            status={t.status}
            canReview={me.role === "REVIEWER" || me.role === "ADMIN"}
            isCreator={me.id === t.created_by_id}
            revisableSteps={revisable}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Execution log ({t.executions.length})</CardTitle>
          <CardDescription>Every delegation, execution, review, revision, escalation, approval and completion.</CardDescription>
        </CardHeader>
        <CardContent>
          <ol className="grid gap-1.5 text-xs">
            {t.executions.map((e) => (
              <li key={e.id} className="grid gap-0.5 border-l-2 pl-2">
                <span>
                  <span className="font-medium">{humanize(e.kind)}</span> · {humanize(e.agent_key)}
                  {e.step_key ? ` · step ${e.step_key}${stepName[e.step_key] ? ` (${stepName[e.step_key]})` : ""}` : ""} ·{" "}
                  {e.status.toLowerCase()}
                  {e.iteration ? ` · iteration ${e.iteration}` : ""}
                  {e.model ? ` · ${e.model}` : ""}
                  {e.latency_ms ? ` · ${e.latency_ms} ms` : ""}
                </span>
                {e.tool_calls.length > 0 && (
                  <span className="text-muted-foreground">tools: {e.tool_calls.map((c) => `${c.tool}${c.ok ? "" : " (failed)"}`).join(", ")}</span>
                )}
                {e.error && <span className="text-destructive">{e.error}</span>}
                {e.ai_run_id && <span className="text-muted-foreground">ai_run {e.ai_run_id.slice(0, 8)}</span>}
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>
      <p className="text-xs">
        <Link href="/organization" className="underline">
          Organization view
        </Link>
      </p>
    </div>
  );
}

export default function TaskPage(props: PageProps<"/tasks/[id]">) {
  return (
    <PageShell title="Task">
      <Suspense fallback={<Loading />}>
        <Detail params={props.params} />
      </Suspense>
    </PageShell>
  );
}
