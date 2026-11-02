import Link from "next/link";
import { Suspense } from "react";

import { CreateTaskForm } from "@/components/app/org-forms";
import { Loading, PageShell } from "@/components/app/page-shell";
import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { humanize, shortDate } from "@/lib/format";
import { type TaskSummary, taskTone } from "@/lib/org";
import { ApiError, api } from "@/lib/server-api";

async function List() {
  let tasks: TaskSummary[];
  try {
    tasks = await api<TaskSummary[]>("/org/tasks");
  } catch (err) {
    return <Alert tone="error">{err instanceof ApiError ? err.detail : "Could not load tasks."}</Alert>;
  }
  if (tasks.length === 0) return <p className="text-sm text-muted-foreground">No tasks yet.</p>;
  return (
    <ul className="divide-y">
      {tasks.map((t) => (
        <li key={t.id} className="grid gap-1 py-3">
          <Link href={`/tasks/${t.id}`} className="font-medium underline-offset-2 hover:underline">
            {t.title}
          </Link>
          <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
            <Badge variant={taskTone(t.status)}>{humanize(t.status)}</Badge>
            <span>{humanize(t.workflow)}</span>
            <span>· approval: {t.approval_level === "HUMAN" ? "human" : "Chief (internal)"}</span>
            <span>
              · {t.executions_used}/{t.max_executions} executions
            </span>
            <span>· {shortDate(t.created_at)}</span>
          </div>
        </li>
      ))}
    </ul>
  );
}

export default function TasksPage() {
  return (
    <PageShell title="Tasks" description="Work assigned to the agent organization. Each task follows a fixed workflow with bounded revisions.">
      <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
        <Card>
          <CardHeader>
            <CardTitle>Recent tasks</CardTitle>
          </CardHeader>
          <CardContent>
            <Suspense fallback={<Loading />}>
              <List />
            </Suspense>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>New task</CardTitle>
          </CardHeader>
          <CardContent>
            <CreateTaskForm />
          </CardContent>
        </Card>
      </div>
    </PageShell>
  );
}
