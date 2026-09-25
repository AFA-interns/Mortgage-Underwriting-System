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

export type DocumentFile = { id: string; filename: string; type: string; size_bytes: number }

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
}

export const documentUrl = (applicationId: string, docId: string): string =>
  `/api/v1/applications/${encodeURIComponent(applicationId)}/documents/${encodeURIComponent(docId)}`

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
