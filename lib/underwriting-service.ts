export type ApplicationStatus = 'In Review' | 'Approved' | 'Needs Review'
export type ReviewStatus = 'Open' | 'In Progress' | 'Resolved'

export type Application = {
  id: string
  borrower: string
  property: string
  type: string
  amount: string
  submitted: string
  status: ApplicationStatus
  risk: string
  score: string
  address: string
  income: string
  decisionAt?: string
  finalDecision?: 'Approved' | 'Declined' | 'Referred'
}

export type Agent = { id: string; name: string; owner: string; status: 'Complete' | 'Hard gate' | 'In progress'; confidence: string; risk: string }
export type ReviewItem = { id: string; title: string; severity: 'High' | 'Medium' | 'Low'; owner: string; status: ReviewStatus; due: string; evidence: string }
export type FinalReport = { id: string; generatedAt: string; recommendation: 'Approve with conditions' | 'Refer to human review'; confidence: string; conditions: string[]; rationale: string[] }

const applications: Application[] = []
const agents: Agent[] = []
const reviewItems: ReviewItem[] = []
let finalReport: FinalReport | null = null

export const underwritingService = {
  async listApplications() { return [...applications] },
  async getApplication(id: string) { return applications.find((app) => app.id === id) ?? null },
  async createApplication(input: Omit<Application, 'id' | 'submitted' | 'status' | 'risk' | 'score'>) {
    const application: Application = { ...input, id: `LN-${new Date().getFullYear()}-${String(applications.length + 1).padStart(4, '0')}`, submitted: new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }), status: 'In Review', risk: 'Pending', score: '—' }
    applications.unshift(application)
    return application
  },
  async listAgents() { return [...agents] },
  async listReviewItems() { return [...reviewItems] },
  async resolveReview(id: string) { const item = reviewItems.find((review) => review.id === id); if (item) item.status = 'Resolved'; return item },
  async getFinalReport() { return finalReport },
  async triggerPropertyValuation(payload: any) {
    try {
      const res = await fetch('/api/v1/valuation/evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      if (!res.ok) throw new Error("Valuation API failed")
      return await res.json()
    } catch (err) {
      console.error("Valuation Agent failed", err)
      return null
    }
  },
}
