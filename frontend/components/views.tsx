'use client'

import { Fragment, useEffect, useMemo, useState } from 'react'
import {
  Activity, AlertCircle, ArrowLeft, ArrowRight, BarChart3, Check, ChevronDown, Clock3, CreditCard,
  ExternalLink, FileCheck2, FileText, GitBranch, Home, Inbox, Loader2, Pencil, Plus, RefreshCw,
  ShieldCheck, Sparkles, UploadCloud, UsersRound, X, Zap, type LucideIcon,
} from 'lucide-react'
import {
  documentUrl, formatInr, formatPct, formatSize, humanizeField, underwritingService,
  type AgentMetricsStatus, type ApplicationView, type ComplianceMetricsReport, type CreditPhase1Report, type DemoScenario,
  type DecisionRuntimeMetrics, type DocumentIngestionMetricsReport, type ParsedDocument,
  type PropertyCoverageReport, type ReviewItem, type Stage, type VersionHistoryEntry,
} from '@/lib/underwriting-service'
import { getDashboardMetrics } from '@/lib/dashboard-service'
import { KeyValues, MetricBar, StatCard, StatusPill, stageTone, statusTone } from '@/components/ui-bits'

export type View = 'dashboard' | 'applications' | 'new' | 'detail' | 'reports' | 'review' | 'final-report' | 'document-review' | 'metrics' | 'analytics' | 'borrowers' | 'documents'

type Nav = { setView: (v: View) => void; open: (id: string) => void }

const STAGE_ICONS = [FileText, CreditCard, Home, ShieldCheck, Sparkles]

const NoApplication = ({ setView, title = 'No application yet' }: { setView: (v: View) => void; title?: string }) => (
  <div className="page-content">
    <div className="panel empty-state">
      <FileText size={25} />
      <strong>{title}</strong>
      <span>Submit an application to run the full underwriting pipeline.</span>
      <button className="primary-button" onClick={() => setView('new')}><Plus size={15} /> New application</button>
    </div>
  </div>
)

/* -------------------------------------------------------------- documents */

function DocumentLinks({ app, onReview }: { app: ApplicationView; onReview?: (docId: string) => void }) {
  if (!app.document_files?.length) return <span className="muted">No stored documents.</span>
  return (
    <ul className="doc-links">
      {app.document_files.map((d) => (
        <li key={d.id}>
          <a href={documentUrl(app.id, d.id)} target="_blank" rel="noreferrer" data-testid="doc-link">
            <FileText size={14} />
            <span>{d.filename.replace(/^\d{2}_/, '')}</span>
            <small>{d.type.replace(/_/g, ' ')} · {formatSize(d.size_bytes)}</small>
          </a>
          {onReview && (
            <button className="doc-review-trigger" data-testid="doc-review-trigger" onClick={() => onReview(d.id)} title="View and correct extracted fields">
              <Pencil size={12} /> Review
            </button>
          )}
        </li>
      ))}
    </ul>
  )
}

/* ---------------------------------------------------------------- tables */

function ApplicationsTable({ apps, open }: { apps: ApplicationView[]; open: (id: string) => void }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr><th>Application</th><th>Borrower</th><th>Loan amount</th><th>Status</th><th>Decision</th><th>Risk score</th><th>Confidence</th></tr>
        </thead>
        <tbody>
          {apps.map((a) => (
            <tr key={a.id} data-testid="application-row" onClick={() => open(a.id)}>
              <td><button className="application-id">{a.id}</button><span className="property-name">{a.property_label}</span></td>
              <td><span className="borrower-cell"><span className="borrower-avatar">{a.borrower.split(' ').map((n) => n[0]).join('').slice(0, 2)}</span>{a.borrower}</span></td>
              <td className="amount">{formatInr(a.loan.amount)}</td>
              <td><StatusPill tone={statusTone(a.status)}>{a.status}</StatusPill></td>
              <td>{a.decision.decision ?? '—'}</td>
              <td><span className={`risk-score ${Number(a.decision.risk_score) < 80 ? 'medium' : ''}`}>{Math.round(a.decision.risk_score ?? 0)}</span></td>
              <td>{formatPct(a.decision.confidence)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/* ------------------------------------------------------------- dashboard */

export function Dashboard({ apps, setView, open }: { apps: ApplicationView[] } & Nav) {
  const m = getDashboardMetrics(apps)
  return (
    <div className="page-content dashboard-page">
      <div className="page-intro">
        <div>
          <p className="section-kicker">Underwriting workspace</p>
          <h2>Underwriting overview</h2>
          <p className="muted">Live results from the five-agent underwriting pipeline.</p>
        </div>
        <button className="primary-button" onClick={() => setView('new')}><Plus size={17} /> New application</button>
      </div>
      <div className="stats-grid">
        <StatCard label="Applications" value={String(m.totalApplications)} detail={`${m.needsReview} need review`} icon={Inbox} tone="blue" />
        <StatCard label="Avg. processing time" value={m.averageProcessing} detail="Full pipeline run" icon={Clock3} tone="mint" />
        <StatCard label="Approval rate" value={m.approvalRate} detail="Of decided applications" icon={Activity} tone="lavender" />
        <StatCard label="Loan book" value={m.portfolioValue} detail="Requested loan amount" icon={CreditCard} tone="amber" />
      </div>
      <div className="panel table-panel">
        <div className="panel-header">
          <div><h3>Recent applications</h3><p>Click an application to open its agent workflow.</p></div>
          <div className="panel-tools"><button className="text-button" onClick={() => setView('applications')}>View all <ArrowRight size={15} /></button></div>
        </div>
        {apps.length === 0 ? (
          <div className="empty-state">
            <Inbox size={25} /><strong>No Applications Yet</strong>
            <span>Create a new application to begin AI-powered underwriting.</span>
            <button className="primary-button" onClick={() => setView('new')}><Plus size={15} /> New application</button>
          </div>
        ) : <ApplicationsTable apps={apps.slice(0, 5)} open={open} />}
      </div>
    </div>
  )
}

export function ApplicationsView({ apps, setView, open }: { apps: ApplicationView[] } & Nav) {
  return (
    <div className="page-content applications-page">
      <div className="page-intro">
        <div><p className="section-kicker">Loan pipeline</p><h2>Applications</h2><p className="muted">{apps.length} total application{apps.length === 1 ? '' : 's'}, newest first.</p></div>
        <button className="primary-button" onClick={() => setView('new')}><Plus size={16} /> New application</button>
      </div>
      <div className="panel table-panel">
        {apps.length === 0 ? <div className="empty-state"><Inbox size={25} /><strong>No Applications Yet</strong></div> : <ApplicationsTable apps={apps} open={open} />}
      </div>
    </div>
  )
}

/* ------------------------------------------------------ new application */

const EMPLOYMENT = ['Salaried', 'Self-employed', 'Business']

export function NewApplication({ setView, onDone }: { setView: (v: View) => void; onDone: (a: ApplicationView) => void }) {
  const [form, setForm] = useState({
    name: '', monthly_income: '', employment_type: 'Salaried', loan_amount: '',
    loan_tenure_months: '240', property_value: '', existing_debt: '0',
    declared_cibil_score: '',
  })
  const [bureauConsent, setBureauConsent] = useState(false)
  const [files, setFiles] = useState<File[]>([])
  const [scenarios, setScenarios] = useState<DemoScenario[]>([])
  const [running, setRunning] = useState<string | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    underwritingService.listDemoScenarios().then(setScenarios).catch(() => setScenarios([]))
  }, [])

  const set = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [key]: e.target.value }))

  const submit = async (data: FormData, label: string) => {
    setError('')
    setRunning(label)
    try {
      onDone(await underwritingService.runApplication(data))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'The pipeline failed.')
    } finally {
      setRunning(null)
    }
  }

  const submitUpload = () => {
    if (!form.name.trim() || !Number(form.monthly_income) || !Number(form.loan_amount)) {
      setError('Borrower name, monthly income and loan amount are required.')
      return
    }
    if (files.length === 0) {
      setError('Upload at least one PDF document, or run a demo scenario.')
      return
    }
    const score = form.declared_cibil_score.trim()
    if (score && (!Number.isInteger(Number(score)) || Number(score) < 300 || Number(score) > 900)) {
      setError('CIBIL score must be a whole number between 300 and 900.')
      return
    }
    const data = new FormData()
    Object.entries(form).forEach(([k, v]) => { if (v !== '') data.append(k, v) })
    data.append('bureau_consent', String(bureauConsent))
    files.forEach((f) => data.append('files', f))
    void submit(data, 'your application')
  }

  const submitDemo = (s: DemoScenario) => {
    const data = new FormData()
    data.append('demo_scenario', s.id)
    void submit(data, s.label)
  }

  return (
    <div className="page-content form-page">
      <div className="page-intro">
        <div><p className="section-kicker">Application intake</p><h2>Start a new application</h2><p className="muted">Enter the loan details and upload the borrower&apos;s documents. Every agent runs on the real files.</p></div>
        <button className="secondary-button" onClick={() => setView('dashboard')}><X size={16} /> Cancel</button>
      </div>

      {running && (
        <div className="run-overlay" role="status" data-testid="pipeline-running">
          <Loader2 className="spin" size={28} />
          <strong>Running the underwriting pipeline for {running}…</strong>
          <span>Document ingestion → credit, property &amp; compliance (in parallel) → decision</span>
        </div>
      )}
      {error && <div className="form-error" role="alert">{error}</div>}

      <div className="form-layout">
        <div className="form-main">
          <section className="form-section">
            <div className="form-section-heading"><span className="section-number">01</span><div><h3>Borrower &amp; loan</h3><p>Amounts in INR</p></div></div>
            <div className="input-grid">
              <label className="span-2">Borrower full name (as on the application)<input name="name" value={form.name} onChange={set('name')} placeholder="Aarav Sharma" /></label>
              <label>Monthly income (₹)<input name="monthly_income" type="number" min="0" value={form.monthly_income} onChange={set('monthly_income')} placeholder="150000" /></label>
              <label>Employment type<select name="employment_type" value={form.employment_type} onChange={set('employment_type')}>{EMPLOYMENT.map((o) => <option key={o}>{o}</option>)}</select></label>
              <label>Loan amount (₹)<input name="loan_amount" type="number" min="0" value={form.loan_amount} onChange={set('loan_amount')} placeholder="5000000" /></label>
              <label>Tenure (months)<input name="loan_tenure_months" type="number" min="12" value={form.loan_tenure_months} onChange={set('loan_tenure_months')} /></label>
              <label>Declared property value (₹)<input name="property_value" type="number" min="0" value={form.property_value} onChange={set('property_value')} placeholder="7500000" /></label>
              <label>Existing monthly EMIs (₹)<input name="existing_debt" type="number" min="0" value={form.existing_debt} onChange={set('existing_debt')} /></label>
              <label>CIBIL score (optional)<input name="declared_cibil_score" type="number" min="300" max="900" value={form.declared_cibil_score} onChange={set('declared_cibil_score')} placeholder="300–900" /></label>
              <label className="span-2 consent-row"><input type="checkbox" name="bureau_consent" checked={bureauConsent} onChange={(e) => setBureauConsent(e.target.checked)} /> The applicant consents to a credit bureau report being pulled. <small>Leave the score blank to use simulated bureau data, which is not the applicant&apos;s real credit.</small></label>
            </div>
          </section>

          <section className="form-section">
            <div className="form-section-heading"><span className="section-number">02</span><div><h3>Documents</h3><p>PDFs only. Documents are classified automatically: PAN, Aadhaar, salary slips, Form 16, bank statement, property deed.</p></div></div>
            <div className={`upload-card ${files.length ? 'uploaded' : ''}`}>
              <input id="doc-upload" data-testid="doc-upload" type="file" accept=".pdf,application/pdf" multiple
                onChange={(e) => setFiles(Array.from(e.target.files ?? []))} />
              <label htmlFor="doc-upload">
                <span className="upload-icon">{files.length ? <Check size={18} /> : <UploadCloud size={18} />}</span>
                <span><strong>{files.length ? `${files.length} document${files.length === 1 ? '' : 's'} selected` : 'Select PDF documents'}</strong><small>{files.length ? 'Ready for processing' : 'PDF · select several at once'}</small></span>
                <span className="upload-action">{files.length ? 'Change' : 'Browse'}</span>
              </label>
            </div>
            {files.length > 0 && <ul className="file-list">{files.map((f) => <li key={f.name + f.size}><FileText size={14} />{f.name}</li>)}</ul>}
          </section>

          <section className="form-section">
            <div className="form-section-heading"><span className="section-number">03</span><div><h3>Or try a demo scenario</h3><p>Runs the pipeline on bundled mock documents</p></div></div>
            <div className="demo-grid">
              {scenarios.map((s) => (
                <button key={s.id} className="demo-card" data-testid={`demo-${s.id}`} disabled={!!running} onClick={() => submitDemo(s)}>
                  <strong>{s.label}</strong><span>{s.description}</span>
                </button>
              ))}
            </div>
          </section>
        </div>

        <aside className="form-summary">
          <div className="summary-card">
            <div className="summary-icon"><Sparkles size={20} /></div>
            <h3>AI underwriting</h3>
            <p>The pipeline analyses documents, credit, property and compliance, then issues an explainable decision.</p>
            <div className="summary-list"><span><Check size={14} /> Document extraction</span><span><Check size={14} /> Credit &amp; risk assessment</span><span><Check size={14} /> Live property valuation</span><span><Check size={14} /> Compliance hard gate</span><span><Check size={14} /> Decision recommendation</span></div>
            <button className="primary-button full" data-testid="start-underwriting" disabled={!!running} onClick={submitUpload}><Zap size={16} /> Start AI underwriting</button>
          </div>
        </aside>
      </div>
    </div>
  )
}

/* ---------------------------------------------------------------- detail */

export function Detail({ app, setView, onReviewDocuments }: { app: ApplicationView | null; setView: (v: View) => void; onReviewDocuments?: (docId?: string) => void }) {
  const [active, setActive] = useState(0)
  if (!app) return <NoApplication setView={setView} title="No application selected" />
  const stage: Stage = app.stages[active] ?? app.stages[0]
  const d = app.decision
  const credit = app.agents.credit

  return (
    <div className="page-content detail-page">
      <button className="back-link" onClick={() => setView('applications')}><ArrowLeft size={16} /> Back to applications</button>
      <div className="detail-heading">
        <div>
          <div className="id-line">
            <span data-testid="detail-id">{app.id}</span><StatusPill tone={statusTone(app.status)}>{app.status}</StatusPill>
            {!!app.rerun_count && <span className="revision-badge" data-testid="revision-badge"><GitBranch size={12} /> Corrected · rerun ×{app.rerun_count}</span>}
          </div>
          <h2>{app.borrower}</h2>
          <p className="muted">{app.property_type} · {app.property_label}</p>
        </div>
        <div className="detail-actions">
          {onReviewDocuments && <button className="secondary-button" onClick={() => onReviewDocuments(undefined)}><Pencil size={15} /> Review documents</button>}
          <button className="secondary-button" onClick={() => setView('reports')}>Agent reports</button>
          <button className="primary-button" onClick={() => setView('final-report')}>Final report</button>
        </div>
      </div>

      <div className={`decision-banner ${app.status === 'Approved' ? 'ok' : 'warn'}`} data-testid="decision-banner">
        <div><span>Decision</span><strong>{d.decision ?? '—'}</strong></div>
        <p>{d.rationale}</p>
      </div>

      {!!app.version_history?.length && <VersionHistoryPanel history={app.version_history} />}

      <section className="panel doc-panel" data-testid="doc-panel">
        <div><h3>Submitted documents</h3><p className="muted">Stored source PDFs — open to verify, or review to correct a misread field.</p></div>
        <DocumentLinks app={app} onReview={onReviewDocuments ? (docId) => onReviewDocuments(docId) : undefined} />
      </section>

      <div className="detail-metrics">
        <div><span>Loan amount</span><strong>{formatInr(app.loan.amount)}</strong></div>
        <div><span>Loan-to-value</span><strong>{formatPct(credit.ltv)}</strong></div>
        <div><span>Credit score</span><strong>{credit.cibil_score ?? '—'}</strong></div>
        <div><span>FOIR</span><strong>{formatPct(credit.foir)}</strong></div>
        <div><span>Decision confidence</span><strong className={Number(d.confidence) >= (Number(d.minimum_confidence ?? d.confidence_threshold ?? 0.80)) ? 'metric-green' : ''}>{formatPct(d.confidence)}</strong></div>
      </div>

      <div className="workflow-heading">
        <div><p className="section-kicker">AI underwriting workflow</p><h3>Application analysis</h3></div>
        <span className="processing"><span className="pulse-dot" /> Completed in {app.processing_seconds}s</span>
      </div>
      <div className="workflow-grid">
        <div className="stage-list">
          {app.stages.map((s, i) => {
            const Icon = STAGE_ICONS[i] ?? FileText
            return (
              <button key={s.name} data-testid={`stage-${i}`} className={`stage-card ${active === i ? 'selected' : ''}`} onClick={() => setActive(i)}>
                <span className={`stage-index ${s.status === 'Complete' ? 'complete' : 'progress'}`}>{s.status === 'Complete' ? <Check size={15} /> : i + 1}</span>
                <span className="stage-icon"><Icon size={18} /></span>
                <span className="stage-copy"><strong>{s.name}{s.name === 'Compliance' && <span className="hard-gate">HARD GATE</span>}</strong><small>{s.subtitle}</small></span>
              </button>
            )
          })}
        </div>
        <div className="report-panel">
          <div className="report-header">
            <div><span className="report-label">Stage report</span><h3>{stage.name}</h3></div>
            <StatusPill tone={stageTone(stage.status)}>{stage.status}</StatusPill>
          </div>
          <div className="report-stats"><div><span>Confidence</span><strong>{formatPct(stage.confidence)}</strong></div><div><span>Summary</span><strong>{stage.subtitle}</strong></div></div>
          <div className="report-body">
            {stage.highlights.filter(Boolean).map((h) => (
              <div className="report-check" key={h}><Check size={16} /><div><p>{h}</p></div></div>
            ))}
          </div>
          <button className="text-button report-link" onClick={() => setView('reports')}>View full {stage.name.toLowerCase()} report <ArrowRight size={15} /></button>
        </div>
      </div>
      {app.errors.length > 0 && <div className="risk-callout amber"><strong>Pipeline notes</strong><span>{app.errors.join(' · ')}</span></div>}
    </div>
  )
}

/* ------------------------------------------------------- version history */

function VersionHistoryPanel({ history }: { history: VersionHistoryEntry[] }) {
  const entries = [...history].reverse() // most recent correction first
  return (
    <section className="panel doc-panel" data-testid="version-history-panel">
      <div style={{ width: '100%' }}>
        <h3>Version history</h3>
        <p className="muted">One application id throughout — each correction below is a rerun of this same case, not a new application.</p>
        <div className="compliance-checks" style={{ marginTop: 14 }}>
          {entries.map((entry) => (
            <div key={entry.version} style={{ padding: '13px 15px', borderBottom: '1px solid var(--border)' }}>
              <div className="compliance-row" style={{ padding: 0, border: 0 }}>
                <div>
                  <strong>Version {entry.version}</strong>
                  <span style={{ display: 'flex', alignItems: 'center', gap: 5, color: '#8091a4', fontSize: 11, marginTop: 3 }}>
                    <Clock3 size={12} /> {new Date(entry.created_at).toLocaleString()}
                  </span>
                </div>
                <span style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: '#5b718a' }}>
                  {entry.decision_before ?? '—'} <ArrowRight size={13} />{' '}
                  <strong style={{ color: entry.decision_after === 'APPROVE' ? '#18825e' : '#b84d47' }}>
                    {entry.decision_after ?? '—'}
                  </strong>
                </span>
              </div>
              {entry.field_changes.length > 0 && (
                <div className="field-summary" style={{ marginTop: 10 }}>
                  {entry.field_changes.map((c, i) => (
                    <span key={i}>
                      {humanizeField(c.field)} <small className="muted">({c.document_type.replace(/_/g, ' ')})</small>
                      <b>{String(c.old_value ?? '—')} → {String(c.new_value ?? '—')}</b>
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

/* --------------------------------------------------------- agent reports */

function AgentDetail({ app, id }: { app: ApplicationView; id: string }) {
  const a = app.agents
  if (id === 'document') {
    const doc = a.document
    return (
      <div className="report-detail">
        <div className="report-detail-heading"><div><p className="section-kicker">Document verification</p><h3>Document Ingestion Report</h3></div><StatusPill tone="blue">{formatPct(doc.extraction_confidence)} confidence</StatusPill></div>
        <div className="report-stat-grid">
          <div><span>Documents processed</span><strong>{(doc.documents ?? []).length}</strong></div>
          <div><span>Verification</span><strong>{doc.verification_status ?? '—'}</strong></div>
          <div><span>Missing documents</span><strong>{(doc.missing_documents ?? []).length}</strong></div>
          <div><span>Monthly income (extracted)</span><strong>{formatInr(doc.income?.monthly_income)}</strong></div>
        </div>
        <div className="report-columns">
          <div><h4>Documents</h4><div className="report-list">{(doc.documents ?? []).map((d: { type: string; status: string; filename?: string }, i: number) => <p key={i}><span>{String(d.type).replace(/_/g, ' ')}{d.filename ? ` · ${d.filename.replace(/^\d{2}_/, '')}` : ''}</span><StatusPill tone={d.status === 'processed' ? 'green' : 'amber'}>{d.status}</StatusPill></p>)}</div></div>
          <div><h4>Extracted fields</h4><KeyValues rows={[
            ['Borrower', doc.borrower_identity?.name ?? '—'], ['Employer', doc.income?.employer ?? '—'],
            ['KYC status', doc.kyc?.status ?? '—'], ['Salary slips', doc.income?.salary_slips_count ?? '—'],
          ]} /></div>
        </div>
        {(doc.missing_documents ?? []).length > 0 && <div className="risk-callout amber"><strong>Missing documents</strong><span>{doc.missing_documents.join(', ')}</span></div>}
        {(doc.contradictions ?? []).length > 0 && <div className="risk-callout amber"><strong>Cross-document contradictions</strong><span>{doc.contradictions.map((c: { description: string }) => c.description).join(' · ')}</span></div>}
      </div>
    )
  }
  if (id === 'credit') {
    const c = a.credit
    return (
      <div className="report-detail">
        <div className="report-detail-heading"><div><p className="section-kicker">Repayment capacity</p><h3>Credit Analysis Report</h3></div><StatusPill tone="blue">{formatPct(c.confidence)} confidence</StatusPill></div>
        <div className="report-stat-grid">
          <div><span>CIBIL score</span><strong>{c.cibil_score ?? '—'}</strong></div><div><span>Credit band</span><strong>{c.credit_band ?? '—'}</strong></div>
          <div><span>FOIR</span><strong>{formatPct(c.foir, 1)}</strong></div><div><span>LTV</span><strong>{formatPct(c.ltv, 1)}</strong></div>
          <div><span>Monthly obligations</span><strong>{formatInr(c.monthly_obligations)}</strong></div><div><span>Proposed EMI</span><strong>{formatInr(c.raw_data?.proposed_emi)}</strong></div>
        </div>
        <div className="credit-bars">
          <MetricBar label="CIBIL score" value={`${c.cibil_score ?? '—'} / 900`} score={((c.cibil_score ?? 0) / 900) * 100} tone="green" />
          <MetricBar label={`FOIR (limit ${formatPct(c.raw_data?.foir_threshold)})`} value={formatPct(c.foir, 1)} score={((c.foir ?? 0) / (c.raw_data?.foir_threshold || 0.55)) * 100} tone="blue" />
          <MetricBar label="Composite credit risk score" value={`${c.risk_score ?? '—'} / 100`} score={c.risk_score ?? 0} tone="green" />
        </div>
        {c.raw_data?.bureau_source && c.raw_data.bureau_source !== 'bureau' && (
          <div className="risk-callout amber" data-testid="bureau-source-note"><strong>Bureau data: {c.raw_data.bureau_source_label}</strong><span>{c.raw_data.bureau_source === 'applicant_declared' ? 'The score was entered manually and has not been verified with a credit bureau; other bureau fields use neutral defaults.' : 'This is not a real credit report, so the credit outcome should not be relied on for an actual lending decision.'}</span></div>
        )}
        <div className="calculation-note"><strong>Reasoning</strong><span>{c.reasoning}</span></div>
        {(c.flags ?? []).length > 0 && <div className="risk-callout amber"><strong>Red flags</strong><span>{c.flags.join(' · ')}</span></div>}
      </div>
    )
  }
  if (id === 'property') {
    const p = a.property
    const comps: Array<Record<string, any>> = (p.comparables ?? []).slice(0, 8)
    return (
      <div className="report-detail">
        <div className="report-detail-heading"><div><p className="section-kicker">Market evidence · live AVnester listings</p><h3>Property Valuation Report</h3></div><StatusPill tone={p.estimated_value > 0 ? 'blue' : 'amber'}>{formatPct(p.valuation_confidence)} confidence</StatusPill></div>
        <div className="property-profile">
          <div><span>Property</span><strong>{app.property_type}</strong><small>{app.property_label}</small></div>
          <div><span>Estimated value</span><strong>{formatInr(p.estimated_value)}</strong><small>Range {formatInr(p.market_range_low)} – {formatInr(p.market_range_high)}</small></div>
          <div><span>₹ / sq.ft. (median)</span><strong>{p.price_per_sqft ? `₹${Math.round(p.price_per_sqft).toLocaleString('en-IN')}` : '—'}</strong><small>{(p.comparables ?? []).length} comparables · {p.scope ?? '—'}-level</small></div>
        </div>
        {comps.length > 0 && <><h4>Comparable listings</h4><div className="table-wrap report-table"><table><thead><tr><th>Listing</th><th>Locality</th><th>Area</th><th>Price</th><th>₹ / sq.ft.</th></tr></thead><tbody>{comps.map((c, i) => <tr key={c.listing_id ?? c.id ?? c.source_url ?? i}><td>{c.title ?? c.property_type ?? '—'}</td><td>{c.locality}</td><td>{Math.round(c.area_sqft).toLocaleString('en-IN')} sq.ft.</td><td>{formatInr(c.price_inr)}</td><td>₹{Math.round(c.price_per_sqft_inr).toLocaleString('en-IN')}</td></tr>)}</tbody></table></div></>}
        {p.location?.formatted_address && <div className="calculation-note"><strong>Geocoded location</strong><span>{p.location.formatted_address}</span></div>}
        <div className="calculation-note"><strong>Explanation</strong><span>{p.explanation}</span></div>
        {(p.flags ?? []).length > 0 && <div className="risk-callout amber"><strong>Valuation risk flags</strong><span>{p.flags.join(' · ')}</span></div>}
      </div>
    )
  }
  if (id === 'compliance') {
    const c = a.compliance
    const critical: string[] = c.critical_flags ?? []
    const reasoning = (c.evidence ?? []).find((e: { field: string }) => e.field === 'reasoning')?.value
    const tone = (s: string) => (s === 'PASS' ? 'green' : s === 'WARNING' || s === 'FAIL' ? 'amber' : 'slate')
    return (
      <div className="report-detail compliance-detail">
        <div className="hard-gate-banner"><ShieldCheck size={24} /><div><strong>REGULATORY COMPLIANCE GATE</strong><span>{critical.length ? 'HARD GATE · Automatic approval blocked until critical issues are resolved.' : 'HARD GATE · Cleared, no critical flags.'}</span></div><StatusPill tone={critical.length ? 'amber' : 'green'}>{critical.length ? 'BLOCKED' : 'CLEAR'}</StatusPill></div>
        <div className="report-detail-heading"><div><p className="section-kicker">Policy controls</p><h3>Compliance Report</h3></div><StatusPill tone="blue">{formatPct(c.confidence)} confidence</StatusPill></div>
        <div className="compliance-checks">{Object.entries(c.rule_status ?? {}).map(([name, status]) => <div className="compliance-row" key={name}><div><strong>{name.replace(/_/g, ' ').toUpperCase()}</strong></div><StatusPill tone={tone(String(status))}>{String(status)}</StatusPill></div>)}</div>
        {c.nhb?.details && <div className="calculation-note"><strong>NHB priority sector</strong><span>{c.nhb.details}</span></div>}
        {critical.length > 0 && <div className="risk-callout amber"><strong>Critical flags</strong><span>{critical.join(' · ')}</span></div>}
        {reasoning && <div className="calculation-note"><strong>Explanation</strong><span>{reasoning}</span></div>}
      </div>
    )
  }
  const d = a.decision
  const rep = app.report
  return (
    <div className="report-detail">
      <div className="report-detail-heading"><div><p className="section-kicker">Synthesis</p><h3>Decision Agent Report</h3></div><StatusPill tone={statusTone(app.status)}>{d.decision}</StatusPill></div>
      <div className="report-stat-grid">
        <div><span>Risk score</span><strong>{d.risk_score}</strong></div><div><span>Risk level</span><strong>{d.risk_level}</strong></div>
        <div><span>Confidence</span><strong>{formatPct(d.confidence, 1)}</strong></div><div><span>Compliance</span><strong>{d.compliance_status}</strong></div>
      </div>
      <div className="credit-bars">{(rep.risk_score_section?.components ?? []).map((c: { name: string; raw_score: number; weight: number }) => <MetricBar key={c.name} label={`${c.name.replace(/_/g, ' ')} (weight ${Math.round(c.weight * 100)}%)`} value={`${c.raw_score}`} score={c.raw_score} tone={c.raw_score >= 75 ? 'green' : 'blue'} />)}</div>
      <div className="report-columns">
        <div><h4>Positive factors</h4><ul className="report-bullets positive">{(d.key_positive_factors ?? rep.positive_factors ?? []).map((f: string) => <li key={f}>{f}</li>)}</ul></div>
        <div><h4>Risk factors</h4><ul className="report-bullets">{(d.key_risk_factors ?? []).map((f: string) => <li key={f}>{f}</li>)}</ul></div>
      </div>
      <h4>Agent consensus</h4>
      <KeyValues rows={Object.entries(d.agent_consensus ?? {}).map(([k, v]) => [k.replace(/_/g, ' '), `${(v as any).recommendation} (${formatPct((v as any).confidence)})`] as [string, string])} />
      <div className="calculation-note"><strong>Rationale</strong><span>{d.rationale}</span></div>
    </div>
  )
}

const AGENTS = [
  { id: 'document', name: 'Document Ingestion', icon: FileText, tone: 'blue', stage: 0 },
  { id: 'credit', name: 'Credit Analysis', icon: CreditCard, tone: 'green', stage: 1 },
  { id: 'property', name: 'Property Valuation', icon: Home, tone: 'blue', stage: 2 },
  { id: 'compliance', name: 'Compliance', icon: ShieldCheck, tone: 'amber', stage: 3 },
  { id: 'decision', name: 'Decision', icon: Sparkles, tone: 'blue', stage: 4 },
]

export function AgentReports({ app, setView }: { app: ApplicationView | null; setView: (v: View) => void }) {
  const [selected, setSelected] = useState<string | null>(null)
  if (!app) return <NoApplication setView={setView} title="No agent reports available" />
  return (
    <div className="page-content reports-page">
      <div className="page-intro">
        <div><p className="section-kicker">{app.id} · {app.borrower}</p><h2>Agent reports</h2><p className="muted">The evidence, confidence and risk signals behind every underwriting agent.</p></div>
        <StatusPill tone="blue">5 agents · 1 hard gate</StatusPill>
      </div>
      <div className="agent-grid">
        {AGENTS.map((ag) => {
          const st = app.stages[ag.stage]
          return (
            <article key={ag.id} data-testid={`agent-${ag.id}`} className={`agent-card ${selected === ag.id ? 'selected' : ''}`}>
              <div className="agent-card-top"><span className={`agent-icon ${ag.tone}`}><ag.icon size={20} /></span><StatusPill tone={stageTone(st.status)}>{st.status}</StatusPill></div>
              <h3>{ag.name}</h3>
              <div className="agent-confidence"><span>Confidence</span><strong>{formatPct(st.confidence)}</strong></div>
              <p className="agent-summary">{st.subtitle}</p>
              <button className="secondary-button report-button" onClick={() => setSelected(selected === ag.id ? null : ag.id)}>{selected === ag.id ? 'Close report' : 'View full report'} <ArrowRight size={15} /></button>
            </article>
          )
        })}
      </div>
      {selected && <section className="panel selected-report" data-testid="agent-detail"><AgentDetail app={app} id={selected} /></section>}
    </div>
  )
}

/* ---------------------------------------------------------- human review */

export function HumanReview({ apps, setView, open, onChanged, onReviewDocuments }: { apps: ApplicationView[]; setView: (v: View) => void; open: (id: string) => void; onChanged: () => void; onReviewDocuments?: (appId: string, docId?: string) => void }) {
  const [items, setItems] = useState<ReviewItem[] | null>(null)
  useEffect(() => { underwritingService.listReviewItems().then(setItems).catch(() => setItems([])) }, [])
  if (items === null) return <div className="page-content"><div className="panel loading-state">Loading review queue…</div></div>

  const resolve = async (id: string) => {
    await underwritingService.resolveReview(id)
    setItems(items.map((i) => (i.id === id ? { ...i, status: 'Resolved' } : i)))
    onChanged()
  }
  const open_ = items.filter((i) => i.status === 'Open')
  return (
    <div className="page-content review-page">
      <div className="page-intro">
        <div><p className="section-kicker">Human-in-the-loop controls</p><h2>Human review queue</h2><p className="muted">Exceptions raised by the agents. Resolving records the reviewer&apos;s acceptance of the evidence.</p></div>
        <StatusPill tone="amber">{open_.length} open items</StatusPill>
      </div>
      {items.length === 0 ? (
        <div className="panel empty-state"><ShieldCheck size={25} /><strong>No Applications Require Review</strong><span>Exceptions appear here when an agent flags an application.</span></div>
      ) : (
        <div className="review-list">
          {items.map((item) => (
            <article className="review-card" key={item.id} data-testid="review-item">
              <div className="review-card-top">
                <div><button className="application-id" onClick={() => open(item.application_id)}>{item.application_id}</button><h3>{item.title}</h3></div>
                <StatusPill tone={item.status === 'Resolved' ? 'green' : item.severity === 'High' ? 'amber' : 'blue'}>{item.status}</StatusPill>
              </div>
              <p>{item.evidence}</p>
              {apps.find((a) => a.id === item.application_id) && (
                <div className="review-docs">
                  <span>Documents to check</span>
                  <DocumentLinks
                    app={apps.find((a) => a.id === item.application_id)!}
                    onReview={onReviewDocuments ? (docId) => onReviewDocuments(item.application_id, docId) : undefined}
                  />
                </div>
              )}
              <div className="review-meta"><span>Owner <strong>{item.owner}</strong></span><span>Severity <strong>{item.severity}</strong></span></div>
              {item.status !== 'Resolved'
                ? <button className="secondary-button" onClick={() => resolve(item.id)}><Check size={15} /> Mark resolved</button>
                : <span className="resolved-note"><Check size={15} /> Evidence accepted</span>}
            </article>
          ))}
        </div>
      )}
      <div className="review-next"><div><Sparkles size={20} /><div><strong>Final decision</strong><span>Open an application&apos;s final report to see the recommendation and conditions.</span></div></div><button className="primary-button" onClick={() => setView('final-report')}>Open final report <ArrowRight size={15} /></button></div>
    </div>
  )
}

/* -------------------------------------------------------- document review */
// Standard document-extraction-review layout: the source document on the
// left, its extracted fields as an editable form on the right. A reviewer
// fixes a field OCR or regex extraction got wrong, saves it, and re-runs
// the pipeline — the correction is applied before validation, so it flows
// into every downstream agent exactly as if extraction had gotten it right.

const toDraft = (fields: Record<string, unknown>): Record<string, string> =>
  Object.fromEntries(Object.entries(fields).map(([k, v]) => [k, v === null || v === undefined ? '' : String(v)]))

const normalize = (v: unknown): string => (v === null || v === undefined || v === '' ? '' : String(v))

export function DocumentReview({
  app, initialDocId, setView, onRerun,
}: {
  app: ApplicationView | null
  initialDocId?: string
  setView: (v: View) => void
  onRerun: (newApp: ApplicationView) => void
}) {
  const docs = useMemo(() => app?.document_files ?? [], [app])
  const [activeDocId, setActiveDocId] = useState(initialDocId ?? docs[0]?.id ?? '')
  const [parsed, setParsed] = useState<ParsedDocument | null>(null)
  const [draft, setDraft] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveMessage, setSaveMessage] = useState('')
  const [rerunning, setRerunning] = useState(false)
  const [rerunError, setRerunError] = useState('')

  // Re-sync when the parent hands us a different application or target document.
  useEffect(() => {
    setActiveDocId((prev) => (initialDocId ?? (docs.some((d) => d.id === prev) ? prev : docs[0]?.id)) ?? '')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [app?.id, initialDocId])

  useEffect(() => {
    if (!app || !activeDocId) { setParsed(null); return }
    setLoading(true); setLoadError(''); setSaveMessage('')
    underwritingService.getParsedDocument(app.id, activeDocId)
      .then((p) => { setParsed(p); setDraft(toDraft(p.effective_fields)) })
      .catch((e) => { setParsed(null); setLoadError(e instanceof Error ? e.message : 'No extracted fields for this document.') })
      .finally(() => setLoading(false))
  }, [app?.id, activeDocId])

  const fieldTypes = useMemo(() => {
    const t: Record<string, 'number' | 'text'> = {}
    if (parsed) for (const f of parsed.editable_fields) t[f] = typeof parsed.extracted_fields[f] === 'number' ? 'number' : 'text'
    return t
  }, [parsed])

  const coerce = (field: string, value: string): unknown => {
    if (fieldTypes[field] !== 'number') return value
    if (value.trim() === '') return null
    const n = Number(value)
    return Number.isNaN(n) ? value : n
  }

  const changedFromExtracted = (field: string): boolean =>
    !!parsed && normalize(coerce(field, draft[field] ?? '')) !== normalize(parsed.extracted_fields[field])

  const isDirty = !!parsed && parsed.editable_fields.some(
    (f) => normalize(coerce(f, draft[f] ?? '')) !== normalize(parsed.effective_fields[f])
  )

  const save = async () => {
    if (!app || !parsed) return
    setSaving(true); setSaveMessage('')
    try {
      const overrides: Record<string, unknown> = {}
      for (const f of parsed.editable_fields) if (changedFromExtracted(f)) overrides[f] = coerce(f, draft[f] ?? '')
      const updated = await underwritingService.saveDocumentOverrides(app.id, activeDocId, overrides)
      setParsed(updated)
      setDraft(toDraft(updated.effective_fields))
      setSaveMessage(Object.keys(overrides).length ? 'Corrections saved — re-run to apply them.' : 'Reverted to the original extracted values.')
    } catch (e) {
      setSaveMessage(e instanceof Error ? e.message : 'Could not save corrections.')
    } finally {
      setSaving(false)
    }
  }

  const rerun = async () => {
    if (!app) return
    setRerunning(true); setRerunError('')
    try {
      onRerun(await underwritingService.rerunApplication(app.id))
    } catch (e) {
      setRerunError(e instanceof Error ? e.message : 'Re-run failed.')
    } finally {
      setRerunning(false)
    }
  }

  if (!app) return <NoApplication setView={setView} title="No application to review" />
  const activeDoc = docs.find((d) => d.id === activeDocId)

  return (
    <div className="page-content document-review-page">
      <button className="back-link" onClick={() => setView('detail')}><ArrowLeft size={16} /> Back to {app.id}</button>
      <div className="page-intro">
        <div>
          <p className="section-kicker">{app.id} · {app.borrower}</p>
          <h2>Review documents</h2>
          <p className="muted">Check each document&apos;s extracted fields against the source. Correct anything misread, save it, then re-run the pipeline.</p>
        </div>
        <button className="primary-button" data-testid="rerun-button" disabled={rerunning || docs.length === 0} onClick={rerun}>
          {rerunning ? <Loader2 className="spin" size={16} /> : <RefreshCw size={16} />} Re-run with corrections
        </button>
      </div>
      {rerunError && <div className="form-error" role="alert">{rerunError}</div>}

      {docs.length === 0 ? (
        <div className="panel empty-state"><FileText size={25} /><strong>No stored documents</strong><span>This application has no documents to review.</span></div>
      ) : (
        <>
          <div className="doc-review-tabs" role="tablist">
            {docs.map((d) => (
              <button key={d.id} role="tab" aria-selected={d.id === activeDocId} data-testid={`review-tab-${d.id}`}
                className={`doc-review-tab ${d.id === activeDocId ? 'active' : ''}`} onClick={() => setActiveDocId(d.id)}>
                <span>{d.type.replace(/_/g, ' ')}</span>
                <small>{d.filename.replace(/^\d{2}_/, '')}</small>
                {d.has_parsed_fields === false && <AlertCircle size={12} className="tab-flag" />}
              </button>
            ))}
          </div>

          <div className="doc-review-split">
            <section className="panel doc-review-preview">
              <div className="doc-review-preview-header">
                <span>{activeDoc?.filename.replace(/^\d{2}_/, '') ?? 'Document'}</span>
                <a href={documentUrl(app.id, activeDocId)} target="_blank" rel="noreferrer"><ExternalLink size={13} /> Open in new tab</a>
              </div>
              <iframe title={`${activeDoc?.filename ?? 'document'} preview`} src={documentUrl(app.id, activeDocId)} className="doc-review-iframe" />
            </section>

            <section className="panel doc-review-form">
              {loading && <div className="loading-state">Loading extracted fields…</div>}
              {!loading && loadError && (
                <div className="empty-state small"><AlertCircle size={20} /><strong>No extracted fields</strong><span>{loadError}</span></div>
              )}
              {!loading && !loadError && parsed && (
                <>
                  <div className="doc-review-form-header">
                    <h3>{parsed.doc_type.replace(/_/g, ' ')}</h3>
                    {Object.keys(parsed.overrides).length > 0 && <StatusPill tone="amber">{Object.keys(parsed.overrides).length} corrected</StatusPill>}
                  </div>
                  {parsed.editable_fields.length === 0 ? (
                    <p className="muted">No reviewer-editable fields for this document type.</p>
                  ) : (
                    <div className="field-form">
                      {parsed.editable_fields.map((f) => {
                        const corrected = f in parsed.overrides
                        return (
                          <label key={f} className={`field-row ${corrected ? 'corrected' : ''}`}>
                            <span className="field-label">{humanizeField(f)}{corrected && <span className="field-badge">Corrected</span>}</span>
                            <input
                              type={fieldTypes[f] === 'number' ? 'number' : 'text'}
                              value={draft[f] ?? ''}
                              onChange={(e) => setDraft((prev) => ({ ...prev, [f]: e.target.value }))}
                            />
                            {corrected && <small className="field-hint">Originally extracted: {String(parsed.extracted_fields[f] ?? '—')}</small>}
                          </label>
                        )
                      })}
                    </div>
                  )}
                  <div className="doc-review-form-actions">
                    {saveMessage && <span className="save-message">{saveMessage}</span>}
                    <button className="secondary-button" disabled={saving || !isDirty} onClick={() => void save()}>
                      {saving ? <Loader2 className="spin" size={15} /> : <Check size={15} />} Save corrections
                    </button>
                  </div>
                </>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  )
}

/* ----------------------------------------------------------- final report */

export function FinalReportView({ app, setView }: { app: ApplicationView | null; setView: (v: View) => void }) {
  if (!app) return <NoApplication setView={setView} title="No reports generated" />
  const d = app.decision
  const rep = app.report
  const rationale = String(rep.final_recommendation ?? d.rationale ?? '').split(' | ').filter(Boolean)
  const open = app.review_items.filter((i) => i.status === 'Open')
  const download = () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(app, null, 2)], { type: 'application/json' }))
    const a = document.createElement('a')
    a.href = url; a.download = `${app.id}-report.json`; a.click()
    URL.revokeObjectURL(url)
  }
  return (
    <div className="page-content final-report-page">
      <div className="report-toolbar">
        <div><p className="section-kicker">Decision artifact · {app.id}</p><h2>Final underwriting report</h2><p className="muted">{app.borrower} · generated {new Date(app.created_at).toLocaleString()}</p></div>
        <div><button className="secondary-button" onClick={() => window.print()}><FileText size={15} /> Print report</button><button className="primary-button" onClick={download}><UploadCloud size={15} /> Download JSON</button></div>
      </div>
      <section className="final-hero">
        <div><span className="section-kicker">Decision Agent recommendation</span><h3 data-testid="final-decision">{d.decision}</h3><p>{d.rationale}</p></div>
        <div className="final-confidence"><span>Overall confidence</span><strong>{formatPct(d.confidence, 1)}</strong><StatusPill tone={statusTone(app.status)}>{open.length ? `${open.length} conditions outstanding` : app.status}</StatusPill></div>
      </section>
      <div className="final-report-grid">
        <section className="panel report-section"><h3>Recommendation rationale</h3>{rationale.map((r, i) => <div className="rationale-row" key={i}><span>{String(i + 1).padStart(2, '0')}</span><p>{r}</p><Check size={16} /></div>)}
          {(rep.positive_factors ?? []).map((f: string) => <div className="rationale-row" key={f}><span>＋</span><p>{f}</p><Check size={16} /></div>)}</section>
        <section className="panel report-section"><h3>Conditions to clear</h3>
          {app.review_items.length === 0 ? <div className="condition-row"><ShieldCheck size={16} /><span>None: no exceptions were raised.</span></div>
            : app.review_items.map((i) => <div className="condition-row" key={i.id}><ShieldCheck size={16} /><span>{i.title}: {i.evidence} <b>({i.status})</b></span></div>)}</section>
      </div>
      <section className="panel audit-panel">
        <div><h3>Audit trail</h3><p className="muted">Every agent output is retained with this report.</p></div>
        <div className="audit-steps"><span><strong>5</strong> agents evaluated</span><span><strong>{Object.keys(app.agents.compliance.rule_status ?? {}).length}</strong> policy checks</span><span><strong>{app.documents.length}</strong> documents</span><span><strong>{(app.agents.compliance.critical_flags ?? []).length}</strong> critical flags</span></div>
      </section>
    </div>
  )
}

/* ------------------------------------------------------------ agent metrics */
// Lets a reviewer run (or re-run) each agent's real evaluation benchmark and
// see the result, instead of only ever reading it from a markdown file.
// Agents without a real, labeled benchmark yet say so plainly rather than
// showing a fabricated number - see backend AGENT_METRICS_STATUS.

const METRICS_AGENT_ICONS: Record<string, { icon: LucideIcon; tone: string }> = {
  document_ingestion: { icon: FileText, tone: 'blue' },
  credit: { icon: CreditCard, tone: 'green' },
  property: { icon: Home, tone: 'blue' },
  compliance: { icon: ShieldCheck, tone: 'amber' },
  decision: { icon: Sparkles, tone: 'blue' },
}

function DocumentIngestionMetricsPanel({ report }: { report: DocumentIngestionMetricsReport }) {
  const cls = report.classification
  const cal = report.calibration
  const recon = report.reconciliation
  const ops = report.operational
  return (
    <div className="metrics-report">
      <div className="stats-grid metrics-stats-grid">
        <StatCard label="Classification accuracy" value={formatPct(cls.accuracy)} detail={`${report.sample_size.documents} documents · ${report.sample_size.bundles} bundles`} icon={FileCheck2} tone="blue" />
        <StatCard label="Cost-weighted error" value={report.cost_weighted_error.toFixed(4)} detail="0 is perfect" icon={Activity} tone="amber" />
        <StatCard label="Brier score" value={cal.brier_score.toFixed(4)} detail="Confidence calibration · 0 is perfect" icon={Activity} tone="blue" />
        <StatCard label="Gate-passing error rate" value={cal.gate_passing_error_rate.toFixed(4)} detail={`Wrong cases that cleared the ${formatPct(cal.gate_threshold ?? 0.80)} gate`} icon={AlertCircle} tone="amber" />
        <StatCard label="Contradiction recall / precision" value={`${formatPct(recon.contradiction_recall)} / ${formatPct(recon.contradiction_precision)}`} detail={`${recon.detected_contradictions} of ${recon.total_actual_contradictions} caught`} icon={ShieldCheck} tone="green" />
        <StatCard label="Contradiction handling accuracy" value={formatPct(recon.contradiction_handling_accuracy)} detail="Caught contradiction also routed correctly" icon={ShieldCheck} tone="green" />
        <StatCard label="STP / HITL rate" value={`${formatPct(ops.straight_through_processing_rate)} / ${formatPct(ops.hitl_escalation_rate)}`} detail={`${ops.total_applications} bundles processed`} icon={Sparkles} tone="blue" />
        <StatCard label="HITL routing accuracy" value={formatPct(report.per_bundle.filter((b) => b.hitl_decision_correct).length / Math.max(report.per_bundle.length, 1))} detail={`${report.per_bundle.filter((b) => b.hitl_decision_correct).length} of ${report.per_bundle.length} bundles routed correctly`} icon={Check} tone="green" />
      </div>
      <div className="panel metrics-subpanel">
        <h4>Per-bundle results</h4>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Bundle</th><th>Docs</th><th>Confidence</th><th>HITL (actual / expected)</th><th>Contradictions</th><th>Missing docs</th></tr></thead>
            <tbody>
              {report.per_bundle.map((b) => (
                <tr key={b.bundle}>
                  <td>{b.bundle.replace(/_/g, ' ')}</td>
                  <td>{b.documents}</td>
                  <td>{formatPct(b.overall_confidence)} ({b.confidence_level})</td>
                  <td><StatusPill tone={b.hitl_decision_correct ? 'green' : 'amber'}>{b.requires_human_review ? 'Review' : 'Auto'} / {b.expected_hitl ? 'Review' : 'Auto'}</StatusPill></td>
                  <td>{b.contradictions_detected}</td>
                  <td>{b.missing_mandatory_documents.length ? b.missing_mandatory_documents.join(', ') : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div className="panel metrics-subpanel">
        <h4>Field-level checks (clean-prime bundle)</h4>
        <KeyValues rows={Object.entries(report.field_level_checks_clean_prime).map(([k, v]) => [humanizeField(k), v.toFixed(2)])} />
      </div>
    </div>
  )
}

function DecisionMetricsPanel({ report }: { report: DecisionRuntimeMetrics }) {
  if (report.n_decisions === 0) {
    return <div className="panel empty-state"><Sparkles size={22} /><strong>No decisions audited yet</strong><span>This fills in as applications run through the pipeline - submit or rerun an application, then come back.</span></div>
  }
  return (
    <div className="metrics-report">
      <div className="stats-grid metrics-stats-grid">
        <StatCard label="Decisions audited" value={String(report.n_decisions)} detail={Object.entries(report.decision_distribution).map(([k, v]) => `${k}: ${v}`).join(' · ')} icon={FileCheck2} tone="blue" />
        <StatCard label="Suspend rate" value={formatPct(report.suspend_rate)} detail="Share routed to human review" icon={ShieldCheck} tone="amber" />
        <StatCard label="Auto-decision rate" value={formatPct(report.auto_decision_rate)} detail="Share resolved without review" icon={Sparkles} tone="green" />
        <StatCard label="Mean confidence" value={formatPct(report.mean_confidence)} detail={`${formatPct(report.below_threshold_rate)} below the ${formatPct(report.confidence_threshold ?? 0.80)} threshold`} icon={Activity} tone="blue" />
      </div>
      {Object.keys(report.gate_trigger_counts).length > 0 && (
        <div className="panel metrics-subpanel">
          <h4>Safety gate triggers</h4>
          <KeyValues rows={Object.entries(report.gate_trigger_counts).map(([k, v]) => [k.replace(/_/g, ' '), String(v)])} />
        </div>
      )}
    </div>
  )
}

function CreditMetricsPanel({ report }: { report: CreditPhase1Report }) {
  if (!report.available) {
    return <div className="panel empty-state"><CreditCard size={22} /><strong>Nothing to measure yet</strong><span>{report.reason}</span></div>
  }
  const bureau = report.bureau_source_mix!
  const decisions = report.decision_distribution!
  const flags = report.flag_trigger_rates!
  const agreement = report.agreement_matrix!
  const quality = report.upstream_data_quality_rate!
  const air = report.adverse_impact_ratio?.favourable_approve
  return (
    <div className="metrics-report">
      {bureau.unverified_share_pct > 0 && (
        <div className="hard-gate-banner" style={{ marginBottom: 16 }}>
          <AlertCircle size={18} />
          <div><strong>Read the bureau-source mix first</strong><span>{bureau.unverified_share_pct}% of applications used simulated or declared data, not a real bureau - most other numbers here measure the stub, not real credit risk.</span></div>
        </div>
      )}
      <div className="stats-grid metrics-stats-grid">
        <StatCard label="Applications measured" value={String(report.n_applications)} detail={`${bureau.sources.demo_fixture?.count ?? 0} demo · ${bureau.sources.bureau?.count ?? 0} real bureau`} icon={FileCheck2} tone="blue" />
        <StatCard label="Unverified bureau share" value={formatPct(bureau.unverified_share_pct / 100)} detail={bureau.meets_production_target ? 'No simulated data' : `${bureau.simulated_share_pct}% simulated`} icon={AlertCircle} tone={bureau.meets_production_target ? 'green' : 'amber'} />
        <StatCard label="Credit vs Decision agreement" value={formatPct(agreement.agreement_rate_pct / 100)} detail={`${agreement.severe_conflicts.length} severe conflict(s)`} icon={Sparkles} tone={agreement.severe_conflicts.length ? 'amber' : 'green'} />
        <StatCard label="Upstream data-quality rate" value={formatPct(quality.rate_pct / 100)} detail={`${quality.reviewed} reviewed · ${quality.not_reviewed} not reviewed`} icon={FileText} tone="blue" />
        {air && <StatCard label="Adverse impact ratio (approve)" value={air.air === null ? '—' : air.air.toFixed(2)} detail={air.status.replace(/_/g, ' ')} icon={ShieldCheck} tone={air.flagged ? 'amber' : 'green'} />}
      </div>
      <div className="panel metrics-subpanel">
        <h4>Decision distribution (Credit Agent preliminary call)</h4>
        <KeyValues rows={Object.entries(decisions.decisions).map(([k, v]) => [k, `${v.count} (${v.pct}%)`])} />
      </div>
      <div className="panel metrics-subpanel">
        <h4>Red-flag trigger rates</h4>
        <KeyValues rows={Object.entries(flags.flags).map(([k, v]) => [k.replace(/_/g, ' '), `${v.count} (${v.pct}%)`])} />
      </div>
      {agreement.severe_conflicts.length > 0 && (
        <div className="panel metrics-subpanel">
          <h4>Severe conflicts (Credit APPROVE vs Decision DENY, or reverse)</h4>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Application</th><th>Credit Agent</th><th>Decision Agent</th></tr></thead>
              <tbody>{agreement.severe_conflicts.map((c) => <tr key={c.application_id}><td>{c.application_id}</td><td>{c.credit}</td><td>{c.decision}</td></tr>)}</tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

function PropertyMetricsPanel({ report }: { report: PropertyCoverageReport }) {
  if (!report.available) {
    return <div className="panel empty-state"><Home size={22} /><strong>Nothing to measure yet</strong><span>{report.reason}</span></div>
  }
  const bySource = report.by_source ?? {}
  return (
    <div className="metrics-report">
      <div className="stats-grid metrics-stats-grid">
        <StatCard label="Applications measured" value={String(report.total_applications)} detail="Property valuation attempts" icon={FileCheck2} tone="blue" />
        <StatCard label="Coverage rate" value={formatPct((report.coverage_rate_pct ?? 0) / 100)} detail={`${report.valuations_produced} of ${report.total_applications} produced a valuation`} icon={Home} tone={(report.coverage_rate_pct ?? 0) >= 80 ? 'green' : 'amber'} />
        <StatCard label="No valuation" value={String(report.no_valuation_count)} detail="AVnester, scraped DB and local median all came up empty" icon={AlertCircle} tone={report.no_valuation_count ? 'amber' : 'green'} />
      </div>
      <div className="panel metrics-subpanel">
        <h4>Valuation source (of coverage)</h4>
        {Object.keys(bySource).length === 0
          ? <span className="muted">No valuations produced yet.</span>
          : <KeyValues rows={Object.entries(bySource).map(([k, v]) => [k.replace(/_/g, ' '), String(v)])} />}
      </div>
      {report.accuracy && !report.accuracy.available && (
        <div className="panel empty-state small" style={{ marginTop: 16 }}>
          <AlertCircle size={20} /><strong>PPE10 / PPE20 / MdAPE not available</strong><span>{report.accuracy.reason}</span>
        </div>
      )}
    </div>
  )
}

function ComplianceMetricsPanel({ report }: { report: ComplianceMetricsReport }) {
  if (!report.available) {
    return <div className="panel empty-state"><ShieldCheck size={22} /><strong>Nothing to measure yet</strong></div>
  }
  const golden = report.golden_set
  const names = report.name_matcher
  const gate = golden.summary.gate_ok
  const rule = golden.summary.rule_ok
  return (
    <div className="metrics-report">
      <div className="stats-grid metrics-stats-grid">
        <StatCard label="Golden set cases" value={String(golden.sample_size)} detail="Hand-labeled KYC/identity/PMLA/RERA/NHB cases" icon={FileCheck2} tone="blue" />
        <StatCard label="Decision-gate agreement" value={`${gate.passed}/${gate.total}`} detail={`${gate.pct}% PASS/SUSPEND matched expected`} icon={ShieldCheck} tone={gate.pct === 100 ? 'green' : 'amber'} />
        <StatCard label="Rule-status agreement" value={`${rule.passed}/${rule.total}`} detail={`${rule.pct}% PASS/WARNING/FAIL matched expected`} icon={FileCheck2} tone={rule.pct === 100 ? 'green' : 'amber'} />
        <StatCard label="Name-matcher F1" value={names.f1 === null ? '—' : names.f1.toFixed(2)} detail={`precision ${names.precision === null ? '—' : names.precision.toFixed(2)} · recall ${names.recall === null ? '—' : names.recall.toFixed(2)} (${names.sample_size} pairs)`} icon={UsersRound} tone={names.misses.length ? 'amber' : 'green'} />
      </div>
      <div className="panel metrics-subpanel">
        <h4>Per-flag recall / precision (golden set)</h4>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Flag</th><th>TP</th><th>FN</th><th>FP</th><th>Precision</th><th>Recall</th></tr></thead>
            <tbody>
              {golden.per_flag.map((f) => (
                <tr key={f.code}>
                  <td>{f.code.replace(/_/g, ' ')}</td><td>{f.tp}</td><td>{f.fn}</td><td>{f.fp}</td>
                  <td>{f.precision === null ? '—' : formatPct(f.precision)}</td>
                  <td>{f.recall === null ? '—' : formatPct(f.recall)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {golden.mismatches.length > 0 && (
        <div className="panel metrics-subpanel">
          <h4>Golden-set mismatches</h4>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Case</th><th>Expected gate</th><th>Got gate</th><th>Expected codes</th><th>Got codes</th></tr></thead>
              <tbody>
                {golden.mismatches.map((m) => (
                  <tr key={m.id}>
                    <td>{m.id}</td><td>{m.expected_gate}</td><td>{m.got_gate}</td>
                    <td>{m.expected_codes.join(', ') || '—'}</td><td>{m.got_codes.join(', ') || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      {names.misses.length > 0 && (
        <div className="panel metrics-subpanel">
          <h4>Name-matcher misses (threshold {names.threshold})</h4>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Pair</th><th>Kind</th><th>Name A</th><th>Name B</th><th>Score</th></tr></thead>
              <tbody>
                {names.misses.map((mm) => (
                  <tr key={mm.pair_id}>
                    <td>{mm.pair_id}</td><td>{mm.kind.replace(/_/g, ' ')}</td><td>{mm.name_a}</td><td>{mm.name_b}</td><td>{mm.score.toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

function AgentMetricCard({ status }: { status: AgentMetricsStatus }) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [docReport, setDocReport] = useState<DocumentIngestionMetricsReport | null>(null)
  const [decisionReport, setDecisionReport] = useState<DecisionRuntimeMetrics | null>(null)
  const [creditReport, setCreditReport] = useState<CreditPhase1Report | null>(null)
  const [propertyReport, setPropertyReport] = useState<PropertyCoverageReport | null>(null)
  const [complianceReport, setComplianceReport] = useState<ComplianceMetricsReport | null>(null)
  const meta = METRICS_AGENT_ICONS[status.agent] ?? { icon: Activity, tone: 'blue' }

  const run = async () => {
    setLoading(true); setError('')
    try {
      if (status.agent === 'document_ingestion') setDocReport(await underwritingService.runDocumentIngestionMetrics())
      else if (status.agent === 'decision') setDecisionReport(await underwritingService.getDecisionRuntimeMetrics())
      else if (status.agent === 'credit') setCreditReport(await underwritingService.runCreditMetrics())
      else if (status.agent === 'property') setPropertyReport(await underwritingService.runPropertyMetrics())
      else if (status.agent === 'compliance') setComplianceReport(await underwritingService.runComplianceMetrics())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not run this benchmark.')
    } finally {
      setLoading(false)
    }
  }

  const hasResult = docReport || decisionReport || creditReport || propertyReport || complianceReport

  return (
    <article className="panel metrics-agent-card" data-testid={`metrics-${status.agent}`}>
      <div className="agent-card-top">
        <span className={`agent-icon ${meta.tone}`}><meta.icon size={20} /></span>
        <StatusPill tone={status.status === 'runnable' ? 'green' : 'slate'}>{status.status === 'runnable' ? 'Runnable' : 'Not available yet'}</StatusPill>
      </div>
      <h3>{status.label}</h3>
      <p className="agent-summary">{status.description}</p>
      {status.status === 'runnable' && (
        <button className="secondary-button report-button" onClick={run} disabled={loading}>
          {loading ? <Loader2 size={15} className="spin" /> : <RefreshCw size={15} />}
          {loading ? 'Running…' : hasResult ? 'Run again' : 'Run benchmark'}
        </button>
      )}
      {error && <div className="form-error" role="alert">{error}</div>}
      {docReport && <DocumentIngestionMetricsPanel report={docReport} />}
      {decisionReport && <DecisionMetricsPanel report={decisionReport} />}
      {creditReport && <CreditMetricsPanel report={creditReport} />}
      {propertyReport && <PropertyMetricsPanel report={propertyReport} />}
      {complianceReport && <ComplianceMetricsPanel report={complianceReport} />}
    </article>
  )
}

export function AgentMetrics({ setView }: { setView: (v: View) => void }) {
  const [statuses, setStatuses] = useState<AgentMetricsStatus[] | null>(null)
  const [loadError, setLoadError] = useState('')
  useEffect(() => {
    underwritingService.getAgentMetricsOverview().then(setStatuses).catch(() => setLoadError('Cannot reach the underwriting backend.'))
  }, [])

  if (loadError) return <div className="page-content"><div className="form-error" role="alert">{loadError}</div></div>
  if (statuses === null) return <div className="page-content"><div className="panel loading-state">Loading agent metrics…</div></div>

  const runnable = statuses.filter((s) => s.status === 'runnable').length
  return (
    <div className="page-content metrics-page">
      <div className="page-intro">
        <div><p className="section-kicker">Evaluation</p><h2>Agent metrics</h2><p className="muted">Run each agent&apos;s real evaluation benchmark and see the result - no fabricated numbers, and agents without a real benchmark yet say so.</p></div>
        <StatusPill tone="blue">{runnable} of {statuses.length} runnable</StatusPill>
      </div>
      <div className="metrics-agent-grid">
        {statuses.map((s) => <AgentMetricCard key={s.agent} status={s} />)}
      </div>
    </div>
  )
}

/* -------------------------------------------------------------- analytics */
// Deeper, portfolio-wide breakdowns computed from the same application list
// the Dashboard already loads - no new backend calls, same as Dashboard's
// own getDashboardMetrics().

function counts<T extends string>(items: T[]): Record<string, number> {
  return items.reduce((acc, v) => { acc[v] = (acc[v] ?? 0) + 1; return acc }, {} as Record<string, number>)
}

const STAGE_LABELS = ['Document Ingestion', 'Credit Analysis', 'Property Valuation', 'Compliance', 'Decision']

export function Analytics({ apps, setView, open }: { apps: ApplicationView[] } & Nav) {
  if (apps.length === 0) return <NoApplication setView={setView} title="No analytics yet" />

  const decisionCounts = counts(apps.map((a) => a.decision?.decision ?? 'PENDING'))
  const decisionTotal = apps.length

  const stageAvgConfidence = STAGE_LABELS.map((label, i) => {
    const values = apps.map((a) => a.stages?.[i]?.confidence).filter((v): v is number => typeof v === 'number')
    const avg = values.length ? values.reduce((s, v) => s + v, 0) / values.length : null
    return { label, avg }
  })

  const riskScores = apps.map((a) => Number(a.decision?.risk_score)).filter((v) => !isNaN(v))
  const avgRisk = riskScores.length ? riskScores.reduce((s, v) => s + v, 0) / riskScores.length : null
  const highRisk = riskScores.filter((v) => v < 60).length

  const propertyTypeCounts = counts(apps.map((a) => a.property_type || 'Unknown'))
  const employmentTypeCounts = counts(apps.map((a) => a.loan.employment_type || 'Unknown'))
  const docTypeCounts = counts(apps.flatMap((a) => (a.document_files ?? []).map((d) => d.type || 'UNKNOWN')))

  const m = getDashboardMetrics(apps)

  return (
    <div className="page-content analytics-page">
      <div className="page-intro">
        <div><p className="section-kicker">Portfolio insight</p><h2>Analytics</h2><p className="muted">Decision mix, agent confidence and portfolio composition across all {apps.length} applications.</p></div>
        <StatusPill tone="blue">{m.needsReview} need review</StatusPill>
      </div>
      <div className="stats-grid">
        <StatCard label="Applications" value={String(m.totalApplications)} detail={`${m.needsReview} need review`} icon={Inbox} tone="blue" />
        <StatCard label="Approval rate" value={m.approvalRate} detail="Of decided applications" icon={Check} tone="mint" />
        <StatCard label="Avg. risk score" value={avgRisk === null ? '—' : avgRisk.toFixed(1)} detail={`${highRisk} below 60`} icon={AlertCircle} tone="amber" />
        <StatCard label="Loan book" value={m.portfolioValue} detail="Requested loan amount" icon={CreditCard} tone="lavender" />
      </div>
      <div className="report-columns" style={{ marginTop: 20 }}>
        <section className="panel report-section">
          <h3>Decision mix</h3>
          {Object.entries(decisionCounts).map(([k, v]) => (
            <MetricBar key={k} label={k} value={`${v} (${Math.round((v / decisionTotal) * 100)}%)`} score={(v / decisionTotal) * 100} tone={k === 'APPROVE' ? 'green' : undefined} />
          ))}
        </section>
        <section className="panel report-section">
          <h3>Average agent confidence</h3>
          {stageAvgConfidence.map(({ label, avg }) => (
            <MetricBar key={label} label={label} value={avg === null ? '—' : formatPct(avg)} score={avg === null ? 0 : avg * 100} tone={avg !== null && avg < 0.6 ? undefined : 'green'} />
          ))}
        </section>
      </div>
      <div className="report-columns" style={{ marginTop: 20 }}>
        <section className="panel report-section">
          <h3>Property type mix</h3>
          <KeyValues rows={Object.entries(propertyTypeCounts).map(([k, v]) => [k, `${v} (${Math.round((v / apps.length) * 100)}%)`])} />
        </section>
        <section className="panel report-section">
          <h3>Employment type mix</h3>
          <KeyValues rows={Object.entries(employmentTypeCounts).map(([k, v]) => [k, `${v} (${Math.round((v / apps.length) * 100)}%)`])} />
        </section>
      </div>
      <section className="panel report-section" style={{ marginTop: 20 }}>
        <h3>Document types across the portfolio</h3>
        <KeyValues rows={Object.entries(docTypeCounts).sort((a, b) => b[1] - a[1]).map(([k, v]) => [k.replace(/_/g, ' '), String(v)])} />
      </section>
      <div className="review-next" style={{ marginTop: 20 }}>
        <div><UsersRound size={20} /><div><strong>Borrowers</strong><span>See every borrower and their application history.</span></div></div>
        <button className="primary-button" onClick={() => setView('borrowers')}>Open borrowers <ArrowRight size={15} /></button>
      </div>
    </div>
  )
}

/* -------------------------------------------------------------- borrowers */
// Derived from the application list - there is no separate borrower entity
// in the backend, so a borrower is "every distinct name on an application."

export function Borrowers({ apps, setView, open }: { apps: ApplicationView[] } & Nav) {
  const [expanded, setExpanded] = useState<string | null>(null)
  if (apps.length === 0) return <NoApplication setView={setView} title="No borrowers yet" />

  const groups = new Map<string, ApplicationView[]>()
  for (const a of apps) {
    const key = a.borrower || 'Unknown borrower'
    groups.set(key, [...(groups.get(key) ?? []), a])
  }
  const borrowers = [...groups.entries()]
    .map(([name, list]) => ({
      name,
      list,
      latest: list[0],
      totalRequested: list.reduce((s, a) => s + (a.loan.amount ?? 0), 0),
    }))
    .sort((a, b) => new Date(b.latest.created_at).getTime() - new Date(a.latest.created_at).getTime())

  return (
    <div className="page-content borrowers-page">
      <div className="page-intro">
        <div><p className="section-kicker">Borrower directory</p><h2>Borrowers</h2><p className="muted">{borrowers.length} borrower{borrowers.length === 1 ? '' : 's'} across {apps.length} application{apps.length === 1 ? '' : 's'}.</p></div>
      </div>
      <div className="panel table-panel">
        <div className="table-wrap">
          <table>
            <thead><tr><th>Borrower</th><th>Applications</th><th>Total requested</th><th>Latest status</th><th>Latest application</th><th /></tr></thead>
            <tbody>
              {borrowers.map((b) => (
                <Fragment key={b.name}>
                  <tr onClick={() => setExpanded(expanded === b.name ? null : b.name)}>
                    <td><span className="borrower-cell"><span className="borrower-avatar">{b.name.split(' ').map((n) => n[0]).join('').slice(0, 2)}</span>{b.name}</span></td>
                    <td>{b.list.length}</td>
                    <td className="amount">{formatInr(b.totalRequested)}</td>
                    <td><StatusPill tone={statusTone(b.latest.status)}>{b.latest.status}</StatusPill></td>
                    <td>{new Date(b.latest.created_at).toLocaleDateString()}</td>
                    <td><ChevronDown size={15} style={{ transform: expanded === b.name ? 'rotate(180deg)' : undefined }} /></td>
                  </tr>
                  {expanded === b.name && (
                    <tr>
                      <td colSpan={6} style={{ background: '#f9fbfd', cursor: 'default' }}>
                        <ul className="doc-links">
                          {b.list.map((a) => (
                            <li key={a.id}>
                              <button className="application-id" onClick={() => open(a.id)}>{a.id}</button>
                              <small> · {a.property_label} · {formatInr(a.loan.amount)} · {a.status}</small>
                            </li>
                          ))}
                        </ul>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

/* -------------------------------------------------------------- documents */
// Flattens every stored document across every application into one list -
// same source data as each application's own "Submitted documents" panel.

export function Documents({ apps, setView, open }: { apps: ApplicationView[] } & Nav) {
  if (apps.length === 0) return <NoApplication setView={setView} title="No documents yet" />

  const docs = apps.flatMap((a) => (a.document_files ?? []).map((d) => ({ ...d, application: a })))
    .sort((a, b) => new Date(b.application.created_at).getTime() - new Date(a.application.created_at).getTime())
  const totalSize = docs.reduce((s, d) => s + (d.size_bytes ?? 0), 0)
  const typeCounts = counts(docs.map((d) => d.type || 'UNKNOWN'))
  const topType = Object.entries(typeCounts).sort((a, b) => b[1] - a[1])[0]

  return (
    <div className="page-content documents-page">
      <div className="page-intro">
        <div><p className="section-kicker">Document store</p><h2>Documents</h2><p className="muted">Every source document ingested across all applications.</p></div>
      </div>
      <div className="stats-grid">
        <StatCard label="Documents" value={String(docs.length)} detail={`Across ${apps.length} application${apps.length === 1 ? '' : 's'}`} icon={FileText} tone="blue" />
        <StatCard label="Storage used" value={formatSize(totalSize)} detail="Stored source PDFs" icon={UploadCloud} tone="mint" />
        <StatCard label="Most common type" value={topType ? topType[0].replace(/_/g, ' ') : '—'} detail={topType ? `${topType[1]} documents` : ''} icon={FileCheck2} tone="lavender" />
        <StatCard label="Distinct types" value={String(Object.keys(typeCounts).length)} detail="Document categories seen" icon={BarChart3} tone="amber" />
      </div>
      <div className="panel table-panel">
        <div className="table-wrap">
          <table>
            <thead><tr><th>Document</th><th>Type</th><th>Size</th><th>Application</th><th>Borrower</th><th>Uploaded</th></tr></thead>
            <tbody>
              {docs.map((d) => (
                <tr key={d.id}>
                  <td><a href={documentUrl(d.application.id, d.id)} target="_blank" rel="noreferrer" className="application-id">{d.filename.replace(/^\d{2}_/, '')}</a></td>
                  <td>{(d.type || 'UNKNOWN').replace(/_/g, ' ')}</td>
                  <td>{formatSize(d.size_bytes ?? 0)}</td>
                  <td><button className="application-id" onClick={() => open(d.application.id)}>{d.application.id}</button></td>
                  <td>{d.application.borrower}</td>
                  <td>{new Date(d.application.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
