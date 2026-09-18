// Types matching the backend API JSON (team/CONTRACTS.md). Adarsh owns this file.

export const DISCLAIMER = "Educational prototype. Not for clinical use.";

export type RunStatus =
  | "running"
  | "ingested"
  | "routed"
  | "awaiting_review"
  | "revising"
  | "approved"
  | "approved_with_edits"
  | "finalized"
  | "ingest_failed";

export type Urgency = "routine" | "critical";

export interface CaseSummary {
  case_id: string;
  title: string;
  specialty: string;
  urgency: Urgency | string;
  description?: string;
  report_path?: string | null;
  lab_path?: string | null;
}

export interface CaseDetail extends CaseSummary {
  report_text: string;
}

export interface LabFlag {
  analyte: string;
  value: string;
  unit?: string;
  flag: "normal" | "high" | "low" | "critical_high" | "critical_low" | "unknown" | string;
}

export interface Recommendation {
  title: string;
  detail: string;
  citations: string[];
}

export interface RunEvent {
  timestamp: string;
  agent: string;
  decision: string;
  latency_ms?: number;
  tokens?: number;
  model?: string;
  tool_calls?: string[];
  error?: string | null;
  payload?: Record<string, unknown>;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp?: string;
}

export interface HumanDecision {
  decision: "pending" | "approve" | "edit" | "reject";
  edits?: string;
  feedback?: string;
  decided_at?: string | null;
}

export interface RunRecord {
  run_id: string;
  case_id: string | null;
  status: RunStatus | string;
  disclaimer?: string;
  summary: string;
  recommendations: Recommendation[];
  lab_flags: LabFlag[];
  retrieved_docs: Record<string, unknown>[];
  safety_flags: string[];
  citations: Record<string, unknown>[];
  analysis: Record<string, unknown>;
  events: RunEvent[];
  chat_history: ChatMessage[];
  human_decision: HumanDecision;
  created_at: string;
  updated_at: string;
  errors?: string[];
}

export interface HealthInfo {
  status: string;
  disclaimer: string;
  mock_llm?: boolean;
  live_llm?: boolean;
}

export interface Metrics {
  runs_total: number;
  runs_finalized: number;
  hitl_approvals: number;
  hitl_rejections: number;
  llm_fallbacks: number;
  agent_latency_ms_avg: number;
  tokens_total: number;
}

export interface ReviewPayload {
  decision: "approve" | "edit" | "reject";
  edits?: string;
  feedback?: string;
}

export interface StartRunResponse {
  run_id: string;
  status: string;
}
