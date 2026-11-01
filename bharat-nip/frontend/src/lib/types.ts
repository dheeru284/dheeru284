/** Types mirroring backend/app/schemas/api.py and app/services/factcheck.py. */

export type Role = "ADMIN" | "REVIEWER" | "ANALYST" | "SUBMITTER";

export const CLASSIFICATIONS = [
  "TRUE",
  "MOSTLY_TRUE",
  "MISLEADING",
  "OUT_OF_CONTEXT",
  "FALSE",
  "UNVERIFIED",
  "INSUFFICIENT_EVIDENCE",
  "OPINION",
  "PREDICTION",
  "SATIRE",
] as const;
export type Classification = (typeof CLASSIFICATIONS)[number];

export type ReviewStatus =
  | "NOT_READY"
  | "PENDING_REVIEW"
  | "APPROVED"
  | "REJECTED"
  | "NEEDS_MORE_RESEARCH";

export type User = { id: string; email: string; display_name: string; role: Role; is_active: boolean };

export type Page<T> = { items: T[]; next_cursor: string | null };

export type PipelineJob = {
  id: string;
  stage: string;
  status: string;
  attempt: number;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
};

export type Submission = {
  id: string;
  submission_type: string;
  status: string;
  raw_text: string | null;
  source_url: string | null;
  title: string | null;
  publisher_name: string | null;
  metadata: Record<string, unknown>;
  extraction_method: string | null;
  extraction_notes: string | null;
  extracted_chars: number;
  created_at: string;
};

export type ClaimEntity = { name: string; type: string; role: string };

export type Claim = {
  id: string;
  submission_id: string;
  text: string;
  normalized_text: string;
  subject: string;
  predicate: string;
  object: string;
  time_reference: string | null;
  claim_date: string | null;
  location: string | null;
  entities: ClaimEntity[];
  original_source: Record<string, string | null>;
  claim_type: string;
  checkworthy: boolean;
  status: string;
  review_status: ReviewStatus;
  extracted_at: string;
  latest_classification: Classification | null;
  latest_confidence: number | null;
};

export type SubmissionDetail = { submission: Submission; claims: Claim[]; pipeline_jobs: PipelineJob[] };
export type ClaimDetail = { claim: Claim; pipeline_jobs: PipelineJob[]; open_review_task_id: string | null };

export type EvidenceItem = {
  evidence_id: string;
  quote: string;
  stance: string;
  directness: string;
  relevance: number;
  rank_score: number;
  cited: boolean;
  source: {
    source_id: string;
    url: string | null;
    title: string;
    publisher: string | null;
    published_at: string | null;
    retrieved_at: string;
    source_type: string;
    is_primary: boolean;
    authority_level: string;
    content_sha256: string;
  };
};

export type Provenance = {
  ai_run_id: string;
  agent_name: string;
  provider: string;
  model: string;
  prompt_id: string;
  prompt_version: string;
  prompt_sha256: string;
  is_mock: boolean;
} | null;

export type CriticCheck = { check: string; passed: boolean; detail: string; evidence: string[] };
export type Finding = { check: string; severity: string; detail: string; evidence: string[] };

export type FactCheck = {
  classification: Classification;
  confidence: number;
  summary: string;
  reasoning: string;
  supporting_evidence: EvidenceItem[];
  contradicting_evidence: EvidenceItem[];
  missing_information: string[];
  recommended_action: string;
  context_evidence: EvidenceItem[];
  claim_id: string;
  assessment_id: string;
  revision: number;
  produced_by: "AGENT" | "RULE";
  confidence_raw: number | null;
  guardrails: { rule: string; detail: string }[];
  assessment_status: string;
  review_status: ReviewStatus;
  final_classification: Classification | null;
  review_decision: {
    decision: string;
    final_classification: Classification | null;
    notes: string | null;
    reviewer_id: string;
    decided_at: string;
  } | null;
  critic: {
    outcome: string;
    agent_outcome: string;
    outcome_overridden: boolean;
    counter_argument: string;
    suggested_classification: Classification | null;
    checks: CriticCheck[];
    deterministic_findings: Finding[];
    provenance: Provenance;
  } | null;
  provenance: Provenance;
};

export type Assessment = {
  id: string;
  revision: number;
  classification: Classification;
  confidence: number;
  summary: string;
  produced_by: string;
  status: string;
  created_at: string;
  critiques: { outcome: string; summary: string; outcome_overridden: boolean }[];
};

export type SearchQuery = {
  id: string;
  provider: string;
  query_text: string;
  status: string;
  result_count: number;
  error: string | null;
  results: { rank: number; url: string | null; title: string; fetch_status: string; fetch_error: string | null }[];
};

export type AuditEvent = {
  seq: number;
  occurred_at: string;
  actor_type: string;
  actor_id: string;
  action: string;
  entity_type: string;
  entity_id: string;
  payload: Record<string, unknown>;
  hash: string;
};

export type ReviewTask = {
  id: string;
  claim_id: string;
  assessment_id: string | null;
  reason: string;
  reason_detail: string | null;
  priority: number;
  status: string;
  created_at: string;
  claim_text: string | null;
  proposed_classification: Classification | null;
  proposed_confidence: number | null;
  submitted_by_me: boolean;
};
