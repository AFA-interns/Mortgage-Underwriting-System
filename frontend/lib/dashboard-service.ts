import { formatInr, type ApplicationView } from '@/lib/underwriting-service'

export type DashboardMetrics = {
  needsReview: number
  totalApplications: number
  averageProcessing: string
  approvalRate: string
  portfolioValue: string
}

export function getDashboardMetrics(applications: ApplicationView[]): DashboardMetrics {
  const decided = applications.filter((a) => a.status === 'Approved' || a.status === 'Declined')
  const approved = decided.filter((a) => a.status === 'Approved').length
  const portfolio = applications.reduce((total, a) => total + (a.loan.amount ?? 0), 0)
  const avg = applications.length
    ? applications.reduce((sum, a) => sum + a.processing_seconds, 0) / applications.length
    : null

  return {
    needsReview: applications.filter((a) => a.status === 'Needs Review').length,
    totalApplications: applications.length,
    averageProcessing: avg === null ? '—' : `${avg.toFixed(1)}s`,
    approvalRate: decided.length ? `${Math.round((approved / decided.length) * 100)}%` : '—',
    portfolioValue: applications.length ? formatInr(portfolio) : '—',
  }
}
