/** Narrative types (backend/app/api/routes/narratives.py) and pure display helpers. */

export const NARRATIVE_STATUSES = [
  "EMERGING",
  "MONITOR",
  "INVESTIGATE",
  "RESPOND",
  "CORRECT",
  "RESOLVED",
  "ARCHIVED",
] as const;
export type NarrativeStatus = (typeof NARRATIVE_STATUSES)[number];

export const RECOMMENDATIONS = ["ESCALATE", "CORRECT", "INVESTIGATE", "RESPOND", "MONITOR", "IGNORE"] as const;
export type Recommendation = (typeof RECOMMENDATIONS)[number];

export const HARM_CATEGORIES = [
  "NONE",
  "PUBLIC_HEALTH",
  "PUBLIC_SAFETY",
  "ELECTORAL_PROCESS",
  "COMMUNAL_HARMONY",
  "FINANCIAL_FRAUD",
  "OTHER",
] as const;
export const HARM_SEVERITIES = ["UNASSESSED", "NONE", "LOW", "MEDIUM", "HIGH"] as const;
export const OBSERVATION_METRICS = ["MENTIONS", "SHARES", "VIEWS", "ARTICLES", "SEARCH_INTEREST"] as const;
export const RESPONSE_TYPES = [
  "FACT_CHECK",
  "CORRECTION",
  "CLARIFICATION",
  "CONTEXT_NOTE",
  "EXTERNAL_FACT_CHECK",
] as const;

export type NarrativeMetrics = {
  computed_at: string;
  engine_version: string;
  claim_count: number;
  rate_7d: number;
  acceleration: number;
  recurring: boolean;
  evidence_status: string;
  evidence_strength: number;
  public_interest: number;
  momentum: number;
  harm_score: number | null;
  uncertainty: number;
  coverage: number;
  recommendation: Recommendation;
  suggested_status: NarrativeStatus;
  version?: number;
  details: {
    velocity: { count_24h: number; count_7d: number; count_prev_7d: number; rate_24h: number };
    bursts: number;
    observation_growth: number;
    public_interest_indicators: {
      distinct_submissions: number;
      distinct_origins: number;
      channels: number;
      reach: number;
    };
    levels: { public_relevance: string; momentum: string };
    verification: { checkable_claims: number; approved: number; approved_classifications: string[] };
    coverage: { components: Record<string, number>; stale: boolean };
    harm: { category: string; severity: string; signals: { category: string; keywords: string }[] };
    reactivated: boolean;
    recommendation: { rule: string; rationale: string; trace: string[]; escalated: boolean; version: string };
  };
};

export type NarrativeSummary = {
  id: string;
  title: string;
  status: NarrativeStatus;
  origin: "DETECTED" | "MANUAL";
  topic: { id: string; label: string } | null;
  first_seen_at: string;
  last_seen_at: string;
  harm_category: string;
  harm_severity: string;
  metrics: NarrativeMetrics | null;
};

export type EmergingTopic = {
  id: string;
  label: string;
  keywords: string[];
  recent_count: number;
  baseline_weekly: number;
  emerging_since: string | null;
};

export type Dashboard = {
  items: NarrativeSummary[];
  counts: { by_status: Record<string, number>; by_recommendation: Record<string, number> };
  emerging_topics: EmergingTopic[];
};

export type NarrativeDetail = NarrativeSummary & {
  summary: string | null;
  harm_rationale: string | null;
  status_note: string | null;
  status_changed_at: string | null;
  allowed_status_transitions: NarrativeStatus[];
  related: { narrative_id: string; title: string; status: string; type: string; weight: number; details: Record<string, unknown> }[];
  observations: { id: string; observed_at: string; channel: string; metric: string; value: number; source_url: string | null; note: string | null }[];
  responses: { id: string; response_type: string; title: string; url: string | null; channel: string | null; published_at: string }[];
};

export type ClaimHistoryItem = {
  claim_id: string;
  text: string;
  seen_at: string;
  burst: number;
  origin: string | null;
  submission_type: string;
  claim_type: string;
  claim_status: string;
  review_status: string;
  latest_classification: string | null;
  approved_classification: string | null;
  similarity: number | null;
  added_by: string | null;
};

export type TimelineEvent =
  | {
      kind: "EVIDENCE";
      at: string;
      date_basis: "published" | "retrieved";
      claim_id: string;
      claim_ids: string[];
      evidence_id: string;
      stance: string;
      quote: string;
      source: { title: string; url: string | null; publisher: string | null; source_type: string; is_primary: boolean };
    }
  | { kind: "REVIEW_DECISION"; at: string; claim_id: string; decision: string; final_classification: string | null };

export type GraphNode = {
  id: string;
  title: string;
  status: string;
  topic_id: string | null;
  topic_label: string | null;
  claim_count: number;
  recommendation: string | null;
  evidence_status: string | null;
  momentum: number;
};
export type GraphEdge = { id: string; source: string; target: string; type: string; weight: number; details: Record<string, unknown> };
export type NarrativeGraph = { nodes: GraphNode[]; edges: GraphEdge[] };

export type HistoryMatch = {
  claim_id: string;
  text: string;
  similarity: number;
  seen_at: string;
  approved_classification: string | null;
  approved_at: string | null;
  narrative_id: string | null;
};

type Tone = "success" | "warning" | "destructive" | "secondary" | "outline" | "default";

export function recommendationTone(r: string | null | undefined): Tone {
  switch (r) {
    case "ESCALATE":
      return "destructive";
    case "CORRECT":
    case "INVESTIGATE":
      return "warning";
    case "RESPOND":
      return "default";
    case "MONITOR":
      return "secondary";
    default:
      return "outline";
  }
}

export function evidenceTone(s: string | null | undefined): Tone {
  switch (s) {
    case "VERIFIED_FALSE":
      return "destructive";
    case "VERIFIED_TRUE":
      return "success";
    case "CONTESTED":
      return "warning";
    default:
      return "outline";
  }
}

export const EDGE_COLORS: Record<string, string> = {
  SIMILAR: "#6b7280",
  SAME_TOPIC: "#9ca3af",
  SHARES_ENTITY: "#2563eb",
  SHARES_EVIDENCE: "#059669",
  CONTRADICTS: "#dc2626",
};

/**
 * Deterministic layout: one column per topic (sorted by label, "No topic" last), nodes
 * stacked within a column by momentum (highest first) then id.
 */
export function layoutGraph(
  nodes: GraphNode[],
  opts: { columnWidth?: number; rowHeight?: number } = {},
): Record<string, { x: number; y: number }> {
  const columnWidth = opts.columnWidth ?? 300;
  const rowHeight = opts.rowHeight ?? 130;
  const groups = new Map<string, GraphNode[]>();
  for (const n of nodes) {
    const key = n.topic_label ?? "￿";
    groups.set(key, [...(groups.get(key) ?? []), n]);
  }
  const positions: Record<string, { x: number; y: number }> = {};
  [...groups.keys()].sort().forEach((key, col) => {
    const members = groups.get(key)!.sort((a, b) => b.momentum - a.momentum || a.id.localeCompare(b.id));
    members.forEach((n, row) => {
      positions[n.id] = { x: col * columnWidth, y: row * rowHeight };
    });
  });
  return positions;
}

/** Number of distinct bursts in a claim history (a recurring narrative has more than one). */
export function burstCount(history: ClaimHistoryItem[]): number {
  return new Set(history.map((h) => h.burst)).size;
}
