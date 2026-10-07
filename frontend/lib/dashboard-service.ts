import type { Application } from '@/lib/underwriting-service'

export type DashboardMetrics = {
  activeApplications: number
  averageDecisionTime: string
  approvalRate: string
  portfolioValue: string
  comparisons: Partial<Record<'activeApplications' | 'averageDecisionTime' | 'approvalRate' | 'portfolioValue', string>>
}

export function getDashboardMetrics(applications: Application[]): DashboardMetrics {
  const decided = applications.filter((application) => application.decisionAt && application.finalDecision)
  const approved = decided.filter((application) => application.finalDecision === 'Approved').length
  const portfolio = applications.reduce((total, application) => total + (Number(application.amount.replace(/[^0-9.-]/g, '')) || 0), 0)
  const decisionTimes = decided.map((application) => {
    const submitted = Date.parse(application.submitted)
    const decidedAt = Date.parse(application.decisionAt ?? '')
    return submitted && decidedAt ? Math.max(0, decidedAt - submitted) / 3600000 : null
  }).filter((value): value is number => value !== null)
  const averageHours = decisionTimes.length ? decisionTimes.reduce((sum, value) => sum + value, 0) / decisionTimes.length : null

  return {
    activeApplications: applications.filter((application) => application.status !== 'Approved').length,
    averageDecisionTime: averageHours === null ? '—' : `${averageHours.toFixed(1)}h`,
    approvalRate: decided.length ? `${Math.round((approved / decided.length) * 100)}%` : '—',
    portfolioValue: applications.length ? `$${portfolio.toLocaleString('en-US')}` : '—',
    comparisons: {},
  }
}
