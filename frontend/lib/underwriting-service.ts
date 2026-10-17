// Typed client for the FastAPI backend. All calls go through the Next.js
// rewrite (/api/v1/* -> http://127.0.0.1:8000/api/v1/*).

export type StageStatus = 'Complete' | 'Flagged' | 'Hard gate'
export type ApplicationStatus = 'Approved' | 'Declined' | 'Needs Review'

export type Stage = {
  name: string
  confidence: number | null
  status: StageStatus
  subtitle: string
  highlights: string[]
}

export type DocumentFile = { id: string; filename: string; type: string; size_bytes: number; has_parsed_fields?: boolean }

export type ParsedDocument = {
  application_id: string
  document_id: string
  doc_type: string
  editable_fields: string[]
  extracted_fields: Record<string, unknown>
  overrides: Record<string, unknown>
  effective_fields: Record<string, unknown>
}

export type ReviewItem = {
  id: string
  application_id: string
  title: string
  severity: 'High' | 'Medium' | 'Low'
  owner: string
  evidence: string
  status: 'Open' | 'Resolved'
  resolved_at?: string
}

export type FieldChange = {
  document_type: string
  filename: string
  field: string
  old_value: unknown
  new_value: unknown
}

export type VersionHistoryEntry = {
  version: number
  created_at: string
  decision_before: string | null
  decision_after: string | null
  risk_score_before: number | null
  risk_score_after: number | null
  field_changes: FieldChange[]
}

/* eslint-disable @typescript-eslint/no-explicit-any */
export type ApplicationView = {
  id: string
  borrower: string
  created_at: string
  processing_seconds: number
  source: string
  documents: string[]
  document_files: DocumentFile[]
  status: ApplicationStatus
  decision: Record<string, any>
  loan: {
    amount?: number
    tenure_months?: number
    monthly_income?: number
    existing_debt?: number
    employment_type?: string
    declared_property_value?: number
  }
  property_label: string
  property_type: string
  stages: Stage[]
  agents: {
    document: Record<string, any>
    credit: Record<string, any>
    property: Record<string, any>
    compliance: Record<string, any>
    decision: Record<string, any>
  }
  report: Record<string, any>
  errors: string[]
  review_items: ReviewItem[]
  rerun_count?: number
  version_history?: VersionHistoryEntry[]
}

export type DemoScenario = {
  id: string
  label: string
  description: string
  profile: Record<string, any>
}

export type AgentMetricsStatus = {
  agent: 'document_ingestion' | 'decision' | 'credit' | 'property' | 'compliance'
  label: string
  status: 'runnable' | 'unavailable'
  description: string
  endpoint: string | null
  method: 'GET' | 'POST' | null
}

export type DocumentIngestionMetricsReport = {
  sample_size: { bundles: number; documents: number }
  classification: { accuracy: number; balanced_accuracy: number; per_class: Record<string, any>; total_samples: number }
  cost_weighted_error: number
  calibration: { brier_score: number; ece: number; gate_passing_error_rate: number; reliability_bins: Record<string, any>[] }
  reconciliation: {
    contradiction_recall: number
    contradiction_precision: number
    contradiction_f1: number
    contradiction_handling_accuracy: number
    name_matching_accuracy: number
    salary_reconciliation_accuracy: number
    total_actual_contradictions: number
    detected_contradictions: number
  }
  operational: {
    total_applications: number
    straight_through_processing_rate: number
    hitl_escalation_rate: number
    mean_confidence: number
    below_threshold_rate: number
    safety_gate_triggers: Record<string, number>
  }
  per_bundle: Array<{
    bundle: string
    documents: number
    overall_confidence: number
    confidence_level: string
    requires_human_review: boolean
    expected_hitl: boolean
    hitl_decision_correct: boolean
    contradictions_detected: number
    missing_mandatory_documents: string[]
  }>
  field_level_checks_clean_prime: Record<string, number>
}

export type DecisionRuntimeMetrics = {
  n_decisions: number
  decision_distribution: Record<string, number>
  suspend_rate: number
  auto_decision_rate: number
  mean_confidence: number
  below_threshold_rate: number
  gate_trigger_counts: Record<string, number>
  crew_agreement_rate: number | null
}

// CREDIT_METRICS.md Phase 1 - no outcome labels needed.
export type CreditPhase1Report = {
  available: boolean
  reason?: string
  n_applications?: number
  bureau_source_mix?: {
    total: number
    sources: Record<string, { count: number; pct: number }>
    simulated_share_pct: number
    unverified_share_pct: number
    meets_production_target: boolean
  }
  flag_trigger_rates?: {
    total: number
    flags: Record<string, { count: number; pct: number }>
    applications_with_any_flag: number
  }
  decision_distribution?: {
    total: number
    missing_decision: number
    other: number
    decisions: Record<string, { count: number; pct: number }>
  }
  confidence_distribution?: {
    n: number
    histogram: Array<{ bin: string; count: number; pct: number }>
    at_floor_count: number
    at_floor_pct: number
    floor_alert: boolean
    formula_mismatches: Array<{ application_id: string; stored: number; expected: number }>
  }
  agreement_matrix?: {
    compared: number
    skipped: number
    agreement_rate_pct: number
    off_diagonal: Array<{ application_id: string; credit: string; decision: string }>
    severe_conflicts: Array<{ application_id: string; credit: string; decision: string }>
  }
  upstream_data_quality_rate?: {
    reviewed: number
    not_reviewed: number
    overridden: number
    rate_pct: number
    by_field: Record<string, number>
  }
  adverse_impact_ratio?: {
    group_key: string
    threshold: number
    favourable_approve: { air: number | null; status: string; rates_pct: Record<string, number>; flagged: boolean }
    small_groups: string[]
    note: string
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init)
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const underwritingService = {
  listApplications: () => request<ApplicationView[]>('/api/v1/applications'),
  getApplication: (id: string) => request<ApplicationView>(`/api/v1/applications/${encodeURIComponent(id)}`),
  listDemoScenarios: () => request<DemoScenario[]>('/api/v1/demo-scenarios'),
  /** Runs the full pipeline: ingestion -> credit + property + compliance -> decision. */
  runApplication: (form: FormData) => request<ApplicationView>('/api/v1/underwriting/run', { method: 'POST', body: form }),
  listReviewItems: () => request<ReviewItem[]>('/api/v1/review-items'),
  resolveReview: (id: string) =>
    request<ReviewItem>(`/api/v1/review-items/${encodeURIComponent(id)}/resolve`, { method: 'POST' }),
  /** What a document's ingestion extracted, any saved reviewer corrections, and the merge of the two. */
  getParsedDocument: (applicationId: string, docId: string) =>
    request<ParsedDocument>(`/api/v1/applications/${encodeURIComponent(applicationId)}/documents/${encodeURIComponent(docId)}/parsed`),
  /** Saves reviewer corrections for one document. Does not re-run the pipeline by itself. */
  saveDocumentOverrides: (applicationId: string, docId: string, overrides: Record<string, unknown>) =>
    request<ParsedDocument>(`/api/v1/applications/${encodeURIComponent(applicationId)}/documents/${encodeURIComponent(docId)}/parsed`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ overrides }),
    }),
  /** Re-runs the full pipeline with saved corrections applied, producing a new, linked application. */
  rerunApplication: (applicationId: string) =>
    request<ApplicationView>(`/api/v1/applications/${encodeURIComponent(applicationId)}/rerun`, { method: 'POST' }),
  /** Which agents have a real, runnable benchmark right now, and which don't (with why). */
  getAgentMetricsOverview: () => request<AgentMetricsStatus[]>('/api/v1/metrics/overview'),
  /** Runs the real Document Ingestion Agent against this project's own bundled demo scenarios. Takes a few seconds. */
  runDocumentIngestionMetrics: () =>
    request<DocumentIngestionMetricsReport>('/api/v1/metrics/document-ingestion', { method: 'POST' }),
  /** Live runtime metrics from every decision this server has actually audited so far - no labels required. */
  getDecisionRuntimeMetrics: () => request<DecisionRuntimeMetrics>('/evaluation/runtime'),
  /** CREDIT_METRICS.md Phase 1 report, computed live from every stored application - no outcome labels needed. */
  runCreditMetrics: () => request<CreditPhase1Report>('/api/v1/metrics/credit', { method: 'POST' }),
}

export const documentUrl = (applicationId: string, docId: string): string =>
  `/api/v1/applications/${encodeURIComponent(applicationId)}/documents/${encodeURIComponent(docId)}`

const FIELD_LABELS: Record<string, string> = {
  pan_number: 'PAN number', dob: 'Date of birth', aadhaar_number: 'Aadhaar number',
  ifsc_code: 'IFSC code', employer_tan: 'Employer TAN', employee_pan: 'Employee PAN',
  gross_salary_sec17_1: 'Gross salary (Sec 17(1))', total_deductions_chapter_via: 'Deductions (Chapter VI-A)',
}

export const humanizeField = (field: string): string =>
  FIELD_LABELS[field] ?? field.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())

export const formatSize = (bytes: number): string =>
  bytes >= 1e6 ? `${(bytes / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1e3))} KB`

export const formatInr = (value: unknown): string => {
  if (typeof value !== 'number' || !isFinite(value) || value <= 0) return '—'
  if (value >= 1e7) return `₹${(value / 1e7).toFixed(2)} Cr`
  if (value >= 1e5) return `₹${(value / 1e5).toFixed(2)} L`
  return `₹${Math.round(value).toLocaleString('en-IN')}`
}

export const formatPct = (value: unknown, digits = 0): string =>
  typeof value === 'number' && isFinite(value) ? `${(value * 100).toFixed(digits)}%` : '—'
