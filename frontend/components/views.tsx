'use client'

import { useEffect, useState } from 'react'
import {
  Activity, ArrowLeft, ArrowRight, Check, Clock3, CreditCard, FileCheck2, FileText, Home, Inbox,
  Loader2, Plus, ShieldCheck, Sparkles, UploadCloud, X, Zap,
} from 'lucide-react'
import {
  documentUrl, formatInr, formatPct, formatSize, underwritingService,
  type ApplicationView, type DemoScenario, type ReviewItem, type Stage,
} from '@/lib/underwriting-service'
import { getDashboardMetrics } from '@/lib/dashboard-service'
import { KeyValues, MetricBar, StatCard, StatusPill, stageTone, statusTone } from '@/components/ui-bits'

export type View = 'dashboard' | 'applications' | 'new' | 'detail' | 'reports' | 'review' | 'final-report'

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

function DocumentLinks({ app }: { app: ApplicationView }) {
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
  })
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
    const data = new FormData()
    Object.entries(form).forEach(([k, v]) => data.append(k, v))
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

export function Detail({ app, setView }: { app: ApplicationView | null; setView: (v: View) => void }) {
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
          <div className="id-line"><span data-testid="detail-id">{app.id}</span><StatusPill tone={statusTone(app.status)}>{app.status}</StatusPill></div>
          <h2>{app.borrower}</h2>
          <p className="muted">{app.property_type} · {app.property_label}</p>
        </div>
        <div className="detail-actions">
          <button className="secondary-button" onClick={() => setView('reports')}>Agent reports</button>
          <button className="primary-button" onClick={() => setView('final-report')}>Final report</button>
        </div>
      </div>

      <div className={`decision-banner ${app.status === 'Approved' ? 'ok' : 'warn'}`} data-testid="decision-banner">
        <div><span>Decision</span><strong>{d.decision ?? '—'}</strong></div>
        <p>{d.rationale}</p>
      </div>

      <section className="panel doc-panel" data-testid="doc-panel">
        <div><h3>Submitted documents</h3><p className="muted">Stored source PDFs, open them to verify the extracted data.</p></div>
        <DocumentLinks app={app} />
      </section>

      <div className="detail-metrics">
        <div><span>Loan amount</span><strong>{formatInr(app.loan.amount)}</strong></div>
        <div><span>Loan-to-value</span><strong>{formatPct(credit.ltv)}</strong></div>
        <div><span>Credit score</span><strong>{credit.cibil_score ?? '—'}</strong></div>
        <div><span>FOIR</span><strong>{formatPct(credit.foir)}</strong></div>
        <div><span>Decision confidence</span><strong className={Number(d.confidence) >= 0.85 ? 'metric-green' : ''}>{formatPct(d.confidence)}</strong></div>
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
        {comps.length > 0 && <><h4>Comparable listings</h4><div className="table-wrap report-table"><table><thead><tr><th>Listing</th><th>Locality</th><th>Area</th><th>Price</th><th>₹ / sq.ft.</th></tr></thead><tbody>{comps.map((c) => <tr key={c.listing_id}><td>{c.title}</td><td>{c.locality}</td><td>{Math.round(c.area_sqft).toLocaleString('en-IN')} sq.ft.</td><td>{formatInr(c.price_inr)}</td><td>₹{Math.round(c.price_per_sqft_inr).toLocaleString('en-IN')}</td></tr>)}</tbody></table></div></>}
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

export function HumanReview({ apps, setView, open, onChanged }: { apps: ApplicationView[]; setView: (v: View) => void; open: (id: string) => void; onChanged: () => void }) {
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
              {apps.find((a) => a.id === item.application_id) && <div className="review-docs"><span>Documents to check</span><DocumentLinks app={apps.find((a) => a.id === item.application_id)!} /></div>}
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
