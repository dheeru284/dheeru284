import Link from "next/link";
import { Suspense } from "react";

import { OrgChart } from "@/components/app/org-chart";
import { Loading, PageShell } from "@/components/app/page-shell";
import { Alert } from "@/components/ui/alert";
import { ApiError, api } from "@/lib/server-api";
import type { AgentDetail, OrgChart as Chart } from "@/lib/org";

async function Content() {
  let chart: Chart, agents: AgentDetail[];
  try {
    [chart, agents] = await Promise.all([api<Chart>("/org/chart"), api<AgentDetail[]>("/org/agents")]);
  } catch (err) {
    if (err instanceof ApiError && err.status === 403) return <Alert>The organization view is for analysts and above.</Alert>;
    return <Alert tone="error">{err instanceof ApiError ? err.detail : "Could not load the organization."}</Alert>;
  }
  return (
    <div className="grid gap-3">
      <p className="text-sm text-muted-foreground">
        {chart.open_tasks} open task(s). Bounds: {chart.bounds.max_executions_per_task} executions per task, each agent&apos;s own
        iteration limit per step, {chart.bounds.max_human_revisions} human revision requests and{" "}
        {chart.bounds.max_step_retries} retry per escalated step. <Link href="/tasks" className="underline">Tasks</Link>
      </p>
      <OrgChart chart={chart} agents={agents} />
    </div>
  );
}

export default function OrganizationPage() {
  return (
    <PageShell
      title="Agent organization"
      description="Fourteen agents with fixed roles, permissions and limits, working only through explicit workflows. Click an agent for its full definition, performance and recent activity."
    >
      <Suspense fallback={<Loading />}>
        <Content />
      </Suspense>
    </PageShell>
  );
}
