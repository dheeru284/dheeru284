/** Agent organization types (backend/app/org/queries.py) and pure helpers. */

export type AgentStatus = "IDLE" | "WORKING" | "WAITING" | "ESCALATED";

export type Performance = {
  executions: number;
  success_rate: number | null;
  revision_rate: number | null;
  failures: number;
  escalations: number;
  reviews_given: number;
  delegations: number;
  approvals: number;
  mean_latency_ms: number | null;
  tokens: number;
  pipeline_runs: number;
  pipeline_success_rate: number | null;
};

export type Activity = { at: string; kind: string; status: string; task_id: string; task: string };

export type OrgNode = {
  id: string;
  kind: "HUMAN" | "AGENT";
  name: string;
  role: string;
  manager: string | null;
  direct_reports: string[];
  independent?: boolean;
  max_iterations?: number;
  status?: AgentStatus;
  current_task?: { task_id: string; title: string; step: string; task_status: string } | null;
  model?: string;
  performance?: Performance;
  recent_activity?: Activity[];
};

export type OrgChart = {
  nodes: OrgNode[];
  edges: { id: string; source: string; target: string }[];
  bounds: { max_executions_per_task: number; max_human_revisions: number; max_step_retries: number };
  open_tasks: number;
};

export type AgentDetail = OrgNode & {
  key: string;
  responsibilities: string[];
  chain_of_command: string[];
  permissions: string[];
  tools: string[];
  max_input_tokens: number;
  max_output_tokens: number;
  max_iterations: number;
  escalation_rules: { condition: string; target: string; description: string }[];
  pipeline_agents: string[];
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
};

export type TaskSummary = {
  id: string;
  workflow: string;
  title: string;
  status: string;
  approval_level: "MANAGER" | "HUMAN";
  executions_used: number;
  max_executions: number;
  human_revisions: number;
  escalation_reason: string | null;
  created_by_id: string;
  created_at: string;
  completed_at: string | null;
};

export type TaskStep = {
  step_key: string;
  seq: number;
  agent_key: string;
  agent_name: string;
  delegated_by: string;
  depends_on: string[];
  reviewer: string;
  status: string;
  iterations: number;
  max_iterations: number;
  retries: number;
  output: Record<string, unknown> | null;
  feedback: { from: string; summary: string; issues: unknown[] }[];
  escalation: { condition: string; target: string; manager: string | null; detail: string } | null;
};

export type Execution = {
  id: string;
  kind: string;
  status: string;
  agent_key: string;
  step_id: string | null;
  step_key: string | null;
  iteration: number;
  input: Record<string, unknown>;
  output: Record<string, unknown> | null;
  tool_calls: { tool: string; ok: boolean; ms: number; error?: string }[];
  ai_run_id: string | null;
  model: string | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  latency_ms: number | null;
  error: string | null;
  at: string;
};

export type TaskDetail = TaskSummary & {
  input: Record<string, unknown>;
  output: Record<string, unknown> | null;
  steps: TaskStep[];
  executions: Execution[];
  approvals: { approver_type: string; approver: string; decision: string; target_step: string | null; notes: string | null; at: string }[];
};

export function taskTone(status: string): "success" | "destructive" | "warning" | "outline" {
  if (status === "COMPLETED") return "success";
  if (status === "ESCALATED" || status === "FAILED" || status === "REJECTED") return "destructive";
  if (status === "AWAITING_APPROVAL") return "warning";
  return "outline";
}

export const LIFECYCLE = ["DELEGATION", "EXECUTION", "REVIEW", "REVISION", "APPROVAL", "COMPLETION"] as const;

/** Which lifecycle stages a task has reached, from its execution log. */
export function lifecycleReached(executions: Pick<Execution, "kind">[]): Record<(typeof LIFECYCLE)[number], number> {
  const out = Object.fromEntries(LIFECYCLE.map((k) => [k, 0])) as Record<(typeof LIFECYCLE)[number], number>;
  for (const e of executions) if (e.kind in out) out[e.kind as (typeof LIFECYCLE)[number]] += 1;
  return out;
}

export const STATUS_COLORS: Record<string, string> = {
  IDLE: "#9ca3af",
  WORKING: "#2563eb",
  WAITING: "#d97706",
  ESCALATED: "#dc2626",
};

/**
 * Deterministic top-down tree layout: each leaf gets its own column, parents are centered
 * over their children. Children are ordered by id.
 */
export function layoutTree(
  nodes: Pick<OrgNode, "id" | "manager">[],
  opts: { columnWidth?: number; rowHeight?: number } = {},
): Record<string, { x: number; y: number }> {
  const columnWidth = opts.columnWidth ?? 240;
  const rowHeight = opts.rowHeight ?? 190;
  const ids = new Set(nodes.map((n) => n.id));
  const children = new Map<string, string[]>();
  const roots: string[] = [];
  for (const n of nodes) {
    if (n.manager && ids.has(n.manager)) children.set(n.manager, [...(children.get(n.manager) ?? []), n.id]);
    else roots.push(n.id);
  }
  for (const list of children.values()) list.sort();
  roots.sort();
  const pos: Record<string, { x: number; y: number }> = {};
  let nextColumn = 0;
  const place = (id: string, depth: number): number => {
    const kids = children.get(id) ?? [];
    let x: number;
    if (kids.length === 0) {
      x = nextColumn * columnWidth;
      nextColumn += 1;
    } else {
      const xs = kids.map((k) => place(k, depth + 1));
      x = (Math.min(...xs) + Math.max(...xs)) / 2;
    }
    pos[id] = { x, y: depth * rowHeight };
    return x;
  };
  roots.forEach((r) => place(r, 0));
  return pos;
}
