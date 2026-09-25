'use client'

import { useCallback, useEffect, useState } from 'react'
import { underwritingService, type ApplicationView } from '@/lib/underwriting-service'
import { getAuthenticatedUser } from '@/lib/auth-service'
import {
  AgentReports, ApplicationsView, Dashboard, Detail, FinalReportView, HumanReview, NewApplication,
  type View,
} from '@/components/views'
import {
  BarChart3, Bell, ChevronDown, CircleHelp, FileCheck2, FileText, LayoutDashboard, Menu,
  PanelLeftClose, PanelLeftOpen, Plus, Search, ShieldCheck, Sparkles, UserRound, UsersRound,
} from 'lucide-react'

function Logo() {
  return <div className="brand-lockup"><div className="brand-mark"><span /><span /><span /></div><span>PRIME<span className="brand-thin">TECHNIQUE</span></span></div>
}

function Sidebar({ view, setView, collapsed, setCollapsed, count }: { view: View; setView: (v: View) => void; collapsed: boolean; setCollapsed: (v: boolean) => void; count: number }) {
  const nav = [
    { label: 'Dashboard', icon: LayoutDashboard, view: 'dashboard' as View },
    { label: 'Applications', icon: FileCheck2, view: 'applications' as View },
    { label: 'Analytics', icon: BarChart3, view: 'dashboard' as View },
    { label: 'Agent Reports', icon: Sparkles, view: 'reports' as View },
    { label: 'Human Review', icon: ShieldCheck, view: 'review' as View },
    { label: 'Final Reports', icon: FileText, view: 'final-report' as View },
  ]
  return <aside className={`sidebar ${collapsed ? 'is-collapsed' : ''}`}>
    <div className="sidebar-top"><Logo /><button className="icon-button sidebar-toggle" aria-label="Toggle sidebar" onClick={() => setCollapsed(!collapsed)}>{collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}</button></div>
    <div className="workspace-switcher"><div className="workspace-avatar">PT</div><div className="workspace-copy"><strong>Prime Technique</strong><span>Underwriting team</span></div><ChevronDown size={15} /></div>
    <nav className="nav-list" aria-label="Main navigation">{nav.map(item => <button key={item.label} className={`nav-item ${view === item.view && item.label === 'Dashboard' ? 'active' : ''}`} onClick={() => setView(item.view)}><item.icon size={18} /><span>{item.label}</span>{item.label === 'Applications' && count > 0 && <span className="nav-count">{count}</span>}</button>)}</nav>
    <div className="nav-label">Workspace</div>
    <nav className="nav-list"><button className="nav-item" onClick={() => setView('new')}><Plus size={18} /><span>New Application</span></button><button className="nav-item"><UsersRound size={18} /><span>Borrowers</span></button><button className="nav-item"><FileText size={18} /><span>Documents</span></button></nav>
    <div className="sidebar-bottom"><button className="nav-item"><CircleHelp size={18} /><span>Help & Support</span></button></div>
  </aside>
}

function Header({ view, setView, onMenu }: { view: View; setView: (v: View) => void; onMenu: () => void }) { const [profileOpen, setProfileOpen] = useState(false); const user = getAuthenticatedUser();
  const title = view === 'dashboard' ? 'Underwriting overview' : view === 'applications' ? 'Applications' : view === 'new' ? 'New loan application' : view === 'reports' ? 'Agent reports' : view === 'review' ? 'Human review queue' : view === 'final-report' ? 'Final reports' : 'Application details'
  return <header className="topbar"><div className="mobile-menu"><button className="icon-button" onClick={onMenu} aria-label="Open navigation"><Menu size={20} /></button></div><div><div className="eyebrow">Workspace / {view === 'dashboard' ? 'Overview' : view === 'applications' ? 'Applications' : view === 'new' ? 'Applications / New' : view === 'reports' ? 'Agent reports' : view === 'review' ? 'Human review' : view === 'final-report' ? 'Final reports' : 'Application details'}</div><h1>{title}</h1></div><div className="topbar-actions"><div className="search-box"><Search size={16} /><input aria-label="Search applications" placeholder="Search applications" /></div><button className="icon-button has-dot" aria-label="Notifications"><Bell size={18} /></button><div className="profile-menu"><button className="top-user" aria-label="Open profile" onClick={() => setProfileOpen(!profileOpen)}><UserRound size={17} /><ChevronDown size={14} /></button>{profileOpen && <div className="profile-popover">{user ? <span>{user.email}</span> : <button>Sign in</button>}</div>}</div></div></header>
}


export default function UnderwritingApp() {
  const [view, setView] = useState<View>('dashboard')
  const [apps, setApps] = useState<ApplicationView[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [loadError, setLoadError] = useState('')

  const refresh = useCallback(async () => {
    try {
      setApps(await underwritingService.listApplications())
      setLoadError('')
    } catch {
      setLoadError('Cannot reach the underwriting backend. Start it with: uvicorn app.main:app --port 8000')
    }
  }, [])
  useEffect(() => { void refresh() }, [refresh])

  // Reports default to the most recent application when none is selected.
  const current = apps.find((a) => a.id === selectedId) ?? apps[0] ?? null
  const open = (id: string) => { setSelectedId(id); setView('detail') }

  return (
    <div className="app-shell">
      <div className={`mobile-overlay ${mobileOpen ? 'show' : ''}`} onClick={() => setMobileOpen(false)} />
      <div className={mobileOpen ? 'mobile-sidebar-open' : ''}>
        <Sidebar view={view} setView={(v) => { setView(v); setMobileOpen(false) }} collapsed={collapsed} setCollapsed={setCollapsed} count={apps.length} />
      </div>
      <main className="main-area">
        <Header view={view} setView={setView} onMenu={() => setMobileOpen(true)} />
        {loadError && <div className="form-error" role="alert">{loadError}</div>}
        {view === 'dashboard' && <Dashboard apps={apps} setView={setView} open={open} />}
        {view === 'applications' && <ApplicationsView apps={apps} setView={setView} open={open} />}
        {view === 'new' && <NewApplication setView={setView} onDone={(a) => { setApps((prev) => [a, ...prev]); open(a.id) }} />}
        {view === 'detail' && <Detail app={current} setView={setView} />}
        {view === 'reports' && <AgentReports app={current} setView={setView} />}
        {view === 'review' && <HumanReview apps={apps} setView={setView} open={open} onChanged={refresh} />}
        {view === 'final-report' && <FinalReportView app={current} setView={setView} />}
      </main>
    </div>
  )
}
