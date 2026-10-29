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
  recommendations: RecommendationReport;
  comparison: StackComparison;
  /** Null for analyses created before this output existed. */
  architecture: ArchitectureView | null;
  roadmap: Roadmap;
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

export type Complexity = "low" | "medium" | "high";
export type CostBand = "none" | "low" | "medium" | "high";
export type SkillLevel = "beginner" | "intermediate" | "advanced";
export type MatchedBy = "knowledge" | "content" | "both";

export interface ScoreBreakdown {
  relevance: number;
  feasibility: number;
  expected_impact: number;
  effort_penalty: number;
  cost_penalty: number;
  weights: Record<string, number>;
  final: number;
}

export interface Recommendation {
  id: string;
  title: string;
  problem_addressed: string;
  current_approach: string;
  proposed_approach: string;
  reason: string;
  evidence: Evidence[];
  addresses_findings: string[];
  expected_benefits: string[];
  trade_offs: string[];
  complexity: Complexity;
  cost: CostBand;
  skill_level: SkillLevel;
  dependencies: string[];
  implementation_steps: string[];
  validation_method: string;
  matched_by: MatchedBy;
  score: ScoreBreakdown;
  constraint_notes: string[];
}

export interface UserConstraints {
  has_gpu: boolean;
  dataset_rows: number | null;
  skill_level: SkillLevel;
  budget: CostBand;
  needs_deployment: boolean;
  assumptions: string[];
}

export interface RecommendationReport {
  recommendations: Recommendation[];
  weights: Record<string, number>;
  constraints: UserConstraints;
  notes: string[];
  excluded: string[];
}

export type StackVerdict = "keep" | "add" | "replace";

export interface StackEntry {
  name: string;
  category: string;
  verdict: StackVerdict;
  rationale: string;
  evidence: Evidence[];
  introduced_by: string[];
  replaces: string | null;
  migration_complexity: Complexity | null;
  cost: CostBand | null;
}

export interface StackComparison {
  entries: StackEntry[];
  notes: string[];
}

export type NodeKind =
  | "data"
  | "preprocess"
  | "features"
  | "model"
  | "evaluation"
  | "serving"
  | "monitoring"
  | "storage";

export interface GraphNode {
  id: string;
  label: string;
  kind: NodeKind;
  origin: "report" | "proposed";
  detail: string | null;
}

export interface ComponentGraph {
  title: string;
  nodes: GraphNode[];
  edges: { source: string; target: string; label: string }[];
}

export interface ArchitectureView {
  current: ComponentGraph;
  proposed: ComponentGraph;
  current_mermaid: string;
  proposed_mermaid: string;
  notes: string[];
}

export type PhaseId = "trustworthy" | "improve" | "reproducible" | "ship";

export interface RoadmapTask {
  recommendation_id: string;
  title: string;
  why: string;
  steps: string[];
  deliverable: string;
  validation: string;
  complexity: Complexity;
  dependencies: string[];
  addresses_findings: string[];
}

export interface RoadmapPhase {
  id: PhaseId;
  order: number;
  title: string;
  rationale: string;
  tasks: RoadmapTask[];
}

export interface Roadmap {
  phases: RoadmapPhase[];
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
