/**
 * Mirrors backend/app/schemas/*.py.
 *
 * Kept hand-written and deliberately narrow so a backend contract change shows
 * up as a TypeScript error rather than as undefined at runtime.
 */

export type ClaimSource = "stated" | "inferred";

export interface Evidence {
  page: number;
  quote: string;
}

export interface Claim {
  value: string;
  source: ClaimSource;
  evidence: Evidence[];
  reasoning: string | null;
}

export interface DatasetInfo {
  name: Claim | null;
  size: Claim | null;
  source: Claim | null;
  preprocessing: Claim[];
}

export interface TechStack {
  languages: Claim[];
  frameworks: Claim[];
  libraries: Claim[];
  tools: Claim[];
}

export interface EvaluationInfo {
  metrics: Claim[];
  reported_results: Claim[];
  validation_strategy: Claim | null;
}

export interface ProjectProfile {
  title: Claim;
  domain: Claim;
  problem_statement: Claim;
  objectives: Claim[];
  intended_users: Claim[];
  methodology: Claim[];
  algorithms: Claim[];
  dataset: DatasetInfo;
  stack: TechStack;
  evaluation: EvaluationInfo;
  architecture_description: Claim | null;
  stated_limitations: Claim[];
  extraction_notes: string[];
}

export interface UsageInfo {
  input_tokens: number;
  output_tokens: number;
  cached_input_tokens: number;
}

export interface AnalysisProvenance {
  provider: string;
  model: string;
  is_mock: boolean;
  usage: UsageInfo;
}

export interface AnalysisSummary {
  id: string;
  created_at: string;
  filename: string;
  page_count: number;
  status: string;
  title: string | null;
  provenance: AnalysisProvenance;
}

export interface AnalysisDetail extends AnalysisSummary {
  content_type: string;
  profile: ProjectProfile;
  findings: FindingsReport;
  claim_counts: { total: number; stated: number; inferred: number };
  finding_counts: { high: number; medium: number; low: number };
  finding_sources: { total: number; rule: number; model: number };
  warnings: string[];
}

export type FindingKind = "weakness" | "gap";
export type Severity = "high" | "medium" | "low";
export type DetectedBy = "rule" | "model";

export interface Finding {
  title: string;
  category: string;
  kind: FindingKind;
  severity: Severity;
  explanation: string;
  evidence: Evidence[];
  /** For a gap: what was looked for. An absence cannot be quoted. */
  searched_for: string | null;
  detected_by: DetectedBy;
  rule_id: string | null;
}

export interface FindingsReport {
  findings: Finding[];
  notes: string[];
}

export interface UserPublic {
  id: string;
  email: string;
  created_at: string;
}

export interface HealthInfo {
  status: string;
  llm: {
    provider: string;
    model: string;
    api_key_configured: boolean;
    is_mock: boolean;
  };
  embedder: string;
  limits: { max_upload_mb: number; max_pages: number };
  ocr_enabled: boolean;
}
