import type { ReactNode } from 'react'
import type { LucideIcon } from 'lucide-react'
import type { ApplicationStatus, StageStatus } from '@/lib/underwriting-service'

export type Tone = 'blue' | 'green' | 'amber' | 'slate'

export function StatusPill({ children, tone = 'blue' }: { children: ReactNode; tone?: Tone }) {
  return <span className={`status-pill ${tone}`}>{children}</span>
}

export function StatCard({ label, value, detail, icon: Icon, tone }: { label: string; value: string; detail: string; icon: LucideIcon; tone: string }) {
  return (
    <div className="stat-card">
      <div className="stat-top"><span>{label}</span><span className={`stat-icon ${tone}`}><Icon size={17} /></span></div>
      <strong>{value}</strong>
      <div className="stat-meta"><span>{detail}</span></div>
    </div>
  )
}

export function MetricBar({ label, value, score, tone = 'blue' }: { label: string; value: string; score: number; tone?: string }) {
  const width = Math.max(0, Math.min(100, score))
  return (
    <div className="report-metric">
      <div><span>{label}</span><strong>{value}</strong></div>
      <div className="metric-track"><span className={tone} style={{ width: `${width}%` }} /></div>
    </div>
  )
}

export const statusTone = (status: ApplicationStatus): Tone =>
  status === 'Approved' ? 'green' : status === 'Declined' ? 'slate' : 'amber'

export const stageTone = (status: StageStatus): Tone => (status === 'Complete' ? 'green' : 'amber')

export function KeyValues({ rows }: { rows: Array<[string, ReactNode]> }) {
  return (
    <div className="kv-list">
      {rows.map(([k, v]) => (
        <div key={k}><span>{k}</span><b>{v}</b></div>
      ))}
    </div>
  )
}
