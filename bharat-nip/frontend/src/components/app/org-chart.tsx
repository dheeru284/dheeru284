"use client";

import "@xyflow/react/dist/style.css";

import { Background, Controls, Handle, type Node, type NodeProps, Position, ReactFlow } from "@xyflow/react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { humanize, percent, shortDate } from "@/lib/format";
import { type AgentDetail, type OrgChart as Chart, type OrgNode, STATUS_COLORS, layoutTree } from "@/lib/org";

type AgentNodeData = { node: OrgNode; names: Record<string, string>; selected: boolean };

function AgentCard({ data }: NodeProps<Node<AgentNodeData>>) {
  const n = data.node;
  const p = n.performance;
  const color = n.kind === "HUMAN" ? "#111827" : STATUS_COLORS[n.status ?? "IDLE"];
  return (
    <div
      className="w-[220px] rounded-lg border-2 bg-card p-2 text-left text-card-foreground shadow-sm"
      style={{ borderColor: data.selected ? "#2563eb" : color }}
    >
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <div className="flex items-start justify-between gap-1">
        <span className="text-xs font-semibold leading-tight">{n.name}</span>
        {n.kind === "AGENT" ? (
          <span className="rounded px-1 text-[9px] font-semibold text-white" style={{ background: color }}>
            {n.status}
          </span>
        ) : (
          <span className="rounded bg-foreground px-1 text-[9px] font-semibold text-background">HUMAN</span>
        )}
      </div>
      {n.kind === "AGENT" ? (
        <div className="mt-1 grid gap-0.5 text-[10px] text-muted-foreground">
          <span className="truncate">
            {n.current_task ? `Task: ${n.current_task.title} (${n.current_task.step})` : "No current task"}
          </span>
          <span className="truncate">
            Manager: {n.manager ? (data.names[n.manager] ?? n.manager) : "none"} · Reports: {n.direct_reports.length}
          </span>
          {p && (
            <span>
              {p.executions} runs · {percent(p.success_rate)} ok · {p.escalations} esc
              {p.reviews_given ? ` · ${p.reviews_given} reviews` : ""}
              {p.pipeline_runs ? ` · ${p.pipeline_runs} pipeline` : ""}
            </span>
          )}
          {n.recent_activity && n.recent_activity[0] && (
            <span className="truncate">
              Last: {humanize(n.recent_activity[0].kind)} {n.recent_activity[0].status.toLowerCase()}
            </span>
          )}
          {n.independent && <span className="font-medium text-foreground">independent</span>}
        </div>
      ) : (
        <p className="mt-1 text-[10px] text-muted-foreground">{n.role}</p>
      )}
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    </div>
  );
}

const nodeTypes = { agent: AgentCard };

function Panel({ agent, names }: { agent: AgentDetail; names: Record<string, string> }) {
  const p = agent.performance;
  return (
    <aside className="grid gap-3 rounded-lg border p-4 text-sm" aria-label="Agent details">
      <div className="grid gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-base font-semibold">{agent.name}</h2>
          <Badge variant={agent.status === "ESCALATED" ? "destructive" : agent.status === "WORKING" ? "default" : "outline"}>
            {agent.status}
          </Badge>
          {agent.independent && <Badge variant="secondary">independent</Badge>}
        </div>
        <p className="text-muted-foreground">{agent.role}</p>
      </div>
      <dl className="grid gap-x-4 gap-y-1 sm:grid-cols-[max-content_1fr]">
        <dt className="text-muted-foreground">Manager</dt>
        <dd>{agent.manager ? names[agent.manager] : "Human oversight"}</dd>
        <dt className="text-muted-foreground">Direct reports</dt>
        <dd>{agent.direct_reports.length ? agent.direct_reports.map((r) => names[r]).join(", ") : "none"}</dd>
        <dt className="text-muted-foreground">Current task</dt>
        <dd>
          {agent.current_task ? (
            <Link href={`/tasks/${agent.current_task.task_id}`} className="underline">
              {agent.current_task.title}
            </Link>
          ) : (
            "none"
          )}
        </dd>
        <dt className="text-muted-foreground">Model</dt>
        <dd>
          <code>{agent.model}</code>
        </dd>
        <dt className="text-muted-foreground">Limits</dt>
        <dd>
          {agent.max_iterations} iteration(s) per step
          {agent.max_input_tokens ? ` · ${agent.max_input_tokens} input / ${agent.max_output_tokens} output tokens` : ""}
        </dd>
        <dt className="text-muted-foreground">Permissions</dt>
        <dd className="flex flex-wrap gap-1">
          {agent.permissions.map((x) => (
            <Badge key={x} variant="outline">
              {x}
            </Badge>
          ))}
        </dd>
        <dt className="text-muted-foreground">Tools</dt>
        <dd>{agent.tools.length ? agent.tools.join(", ") : "none (prompt only or engine-run)"}</dd>
      </dl>
      <div>
        <h3 className="font-medium">Responsibilities</h3>
        <ul className="list-disc pl-5 text-muted-foreground">
          {agent.responsibilities.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      </div>
      <div>
        <h3 className="font-medium">Escalation rules</h3>
        <ul className="grid gap-0.5 text-xs text-muted-foreground">
          {agent.escalation_rules.map((r) => (
            <li key={r.condition}>
              <code>{r.condition}</code> → {r.target.toLowerCase()}: {r.description}
            </li>
          ))}
        </ul>
      </div>
      {p && (
        <div>
          <h3 className="font-medium">Performance</h3>
          <p className="text-xs text-muted-foreground">
            {p.executions} executions · success {percent(p.success_rate)} · revisions {percent(p.revision_rate)} ·{" "}
            {p.escalations} escalations · {p.reviews_given} reviews given · {p.delegations} delegations · mean{" "}
            {p.mean_latency_ms ?? "—"} ms · {p.tokens} tokens · Phase 1 pipeline runs {p.pipeline_runs} (
            {percent(p.pipeline_success_rate)} ok)
          </p>
        </div>
      )}
      <div>
        <h3 className="font-medium">Recent activity</h3>
        {agent.recent_activity?.length ? (
          <ul className="grid gap-0.5 text-xs">
            {agent.recent_activity.map((a, i) => (
              <li key={`${a.at}-${i}`}>
                {shortDate(a.at)} · {humanize(a.kind)} {a.status.toLowerCase()} ·{" "}
                <Link href={`/tasks/${a.task_id}`} className="underline">
                  {a.task}
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-xs text-muted-foreground">None yet.</p>
        )}
      </div>
    </aside>
  );
}

export function OrgChart({ chart, agents }: { chart: Chart; agents: AgentDetail[] }) {
  const [selected, setSelected] = useState<string>("chief_intelligence_agent");
  const names = useMemo(() => Object.fromEntries(chart.nodes.map((n) => [n.id, n.name])), [chart]);
  const nodes = useMemo(() => {
    const pos = layoutTree(chart.nodes);
    return chart.nodes.map((n) => ({
      id: n.id,
      type: "agent",
      position: pos[n.id],
      data: { node: n, names, selected: n.id === selected },
    }));
  }, [chart, names, selected]);
  const edges = useMemo(
    () => chart.edges.map((e) => ({ ...e, type: "smoothstep", style: { stroke: "#9ca3af" } })),
    [chart],
  );
  const agent = agents.find((a) => a.key === selected);
  return (
    <div className="grid gap-4">
      <div className="grid gap-2">
        <div className="h-[560px] w-full rounded-lg border sm:h-[620px]">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.04 }}
            minZoom={0.15}
            onInit={(instance) => instance.fitView({ padding: 0.04 })}
            nodesDraggable={false}
            nodesConnectable={false}
            onNodeClick={(_, node) => node.id !== "human_oversight" && setSelected(node.id)}
            proOptions={{ hideAttribution: true }}
          >
            <Background />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>
        <ul className="flex flex-wrap gap-3 text-xs text-muted-foreground" aria-label="Status legend">
          {Object.entries(STATUS_COLORS).map(([s, c]) => (
            <li key={s} className="flex items-center gap-1">
              <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: c }} />
              {humanize(s)}
            </li>
          ))}
        </ul>
      </div>
      {agent && <Panel agent={agent} names={names} />}
    </div>
  );
}
