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
  revised_from?: string | null
}

export type DemoScenario = {
  id: string
  label: string
  description: string
  profile: Record<string, any>
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
