import React, { useEffect, useMemo, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './style.css'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/+$/, '')
const SHOW_DEMO_CREDENTIALS = import.meta.env.VITE_SHOW_DEMO_CREDENTIALS === 'true'
const api = async (path, options = {}) => {
  const response = await fetch(API_BASE_URL + path, { ...options, headers: { 'Content-Type': 'application/json', ...(window.__token ? { Authorization: 'Bearer ' + window.__token } : {}) } })
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || 'Request failed')
  return response.json()
}
const download = async (format, mode = 'full', employeeId = '') => {
  const query = '?format=' + encodeURIComponent(format) + '&mode=' + encodeURIComponent(mode) + (employeeId ? '&employee_id=' + encodeURIComponent(employeeId) : '')
  const response = await fetch(API_BASE_URL + '/admin/reports/export' + query, {
    headers: window.__token ? { Authorization: 'Bearer ' + window.__token } : {}
  })
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).detail || 'Could not generate report')
  const blob = await response.blob()
  const disposition = response.headers.get('Content-Disposition') || ''
  const filename = disposition.match(/filename=([^;]+)/i)?.[1]?.replace(/["']/g, '') || ('safeguard-analysis.' + format)
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
const assignmentTitle = title => (title || 'Security awareness campaign').replace(/campaing/gi, 'campaign')

const Logo = () => (
  <div className="logo">
    <span className="logo-mark">S</span>
    <span>Safeguard</span>
  </div>
)

function Login({ onLogin }) {
  const [role, setRole] = useState('client_admin'),
        [email, setEmail] = useState(SHOW_DEMO_CREDENTIALS ? 'admin@demo.securetrain.test' : ''),
        [password, setPassword] = useState(SHOW_DEMO_CREDENTIALS ? 'AdminDemo123!' : ''),
        [error, setError] = useState('')

  const choose = value => {
    setRole(value)
    setEmail(SHOW_DEMO_CREDENTIALS ? (value === 'client_admin' ? 'admin@demo.securetrain.test' : 'employee@demo.securetrain.test') : '')
    setPassword(SHOW_DEMO_CREDENTIALS ? (value === 'client_admin' ? 'AdminDemo123!' : 'EmployeeDemo123!') : '')
  }

  const submit = async event => {
    event.preventDefault()
    setError('')
    try {
      const user = await api('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) })
      window.__token = user.access_token
      onLogin(user)
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <main className="login-page">
      <div className="landing-topline">
        <Logo />
        <div className="landing-status"><span /> Simulation environment ready <b>·</b> Built for safer teams</div>
        <nav className="landing-nav"><a href="#platform">Platform</a><a href="#approach">How it works</a></nav>
        <a href="#signin" onClick={event => { event.preventDefault(); document.querySelector('.login-panel input')?.focus() }}>Member sign in <span>↗</span></a>
      </div>
      <section className="login-panel" id="signin">
        <div className="login-copy">
          <span>YOUR SECURITY WORKSPACE</span>
          <h1>Good instincts are built, not born.</h1>
          <p>Sign in to turn everyday decisions into your team’s strongest line of defense.</p>
        </div>

        <div className="role-tabs">
          <button className={role === 'client_admin' ? 'selected' : ''} onClick={() => choose('client_admin')}>Admin</button>
          <button className={role === 'employee' ? 'selected' : ''} onClick={() => choose('employee')}>Employee</button>
        </div>

        <form onSubmit={submit}>
          <label>
            Work email
            <input value={email} onChange={event => setEmail(event.target.value)} required />
          </label>
          <label>
            Password
            <input type="password" value={password} onChange={event => setPassword(event.target.value)} required />
          </label>
          {error && <p className="form-error">{error}</p>}
          <button className="button button-primary wide">Sign in</button>
        </form>

        <p className="login-footnote"><span className="lock-icon">◇</span> Your workspace is protected with encrypted authentication.</p>
      </section>

      <aside className="login-aside">
        <div className="grid-orb" />
        <div className="hero-kicker"><span className="kicker-pulse" /> SECURITY THAT LEARNS WITH YOU <span className="kicker-index">01 / 03</span></div>
        <div className="hero-art" aria-hidden="true">
          <div className="art-ring ring-one" /><div className="art-ring ring-two" /><div className="art-ring ring-three" />
          <svg viewBox="0 0 500 390" fill="none">
            <path className="orbit-path" d="M65 234C113 113 248 65 373 113c90 35 120 133 61 198-53 58-155 44-175-22-17-54 26-104 74-92 40 10 47 57 22 78" />
            <path className="orbit-path orbit-path-alt" d="M79 111c91 16 144 78 171 134 27 55 65 98 131 96" />
            <circle cx="250" cy="196" r="95" className="core-halo" />
            <path d="M250 136l52 20v43c0 38-22 67-52 82-30-15-52-44-52-82v-43l52-20Z" className="shield-shape" />
            <path d="m228 198 15 15 31-34" className="shield-check" />
            <circle cx="96" cy="111" r="7" className="node node-lime"/><circle cx="373" cy="113" r="6" className="node node-white"/>
            <circle cx="434" cy="311" r="8" className="node node-lime"/><circle cx="75" cy="234" r="5" className="node node-white"/>
            <circle cx="382" cy="173" r="4" className="node node-lime"/><circle cx="187" cy="315" r="4" className="node node-white"/>
          </svg>
          <div className="signal-card signal-one"><span className="signal-icon">↗</span><div><small>THREAT RESPONSE</small><b>Getting sharper</b></div><span className="signal-live">LIVE</span></div>
          <div className="signal-card signal-two"><span className="signal-icon signal-spark">✳</span><div><small>ADAPTIVE LEARNING</small><b>One round at a time</b></div></div>
          <div className="art-caption"><span>FIG 01</span><span>HUMAN + MACHINE, IN SYNC</span></div>
        </div>
        <div className="hero-copy">
          <div className="hero-eyebrow">A new kind of security training</div>
          <h2>Make your people<br />the <span className="highlight">human firewall.</span></h2>
          <p>Realistic simulations. Personal coaching. A team that gets a little harder to fool every day.</p>
        </div>
        <div className="hero-foot"><span>01 — PRACTICE</span><span>02 — LEARN</span><span>03 — PROTECT</span></div>
      </aside>
      <section className="landing-details" id="platform">
        <div className="landing-section-heading">
          <div><span className="landing-overline">THE SAFEGUARD METHOD</span><h2>Training that meets people<br />where the risk actually is.</h2></div>
          <p>Move beyond one-size-fits-all reminders. Safeguard turns realistic practice into useful feedback and a clearer picture of organizational risk.</p>
        </div>
        <div className="landing-feature-grid">
          <article className="landing-feature feature-simulation">
            <div className="feature-number">01 <span>REALISTIC PRACTICE</span></div>
            <div className="mail-preview"><div className="mail-top"><span>INBOX SIMULATION</span><span className="mail-dot" /></div><div className="mail-from"><i>F</i><div><b>Finance Team</b><small>to you · just now</small></div></div><div className="mail-subject">Updated payment details</div><div className="mail-lines"><i /><i /><i /></div><div className="mail-link">Review secure document <span>↗</span></div></div>
            <h3>Practice in context</h3><p>Employees learn by responding to simulated scenarios that reflect common workplace tactics.</p>
          </article>
          <article className="landing-feature feature-adaptive">
            <div className="feature-number">02 <span>ADAPTIVE LEARNING</span></div>
            <div className="adaptive-preview"><div className="adaptive-head"><span>LEARNING PATH</span><b>Adjusting</b></div><div className="adaptive-bars"><span style={{'--bar-height':'42%'}} /><span style={{'--bar-height':'64%'}} /><span className="bar-current" style={{'--bar-height':'88%'}} /><span style={{'--bar-height':'56%'}} /><span style={{'--bar-height':'72%'}} /><span style={{'--bar-height':'47%'}} /></div><div className="adaptive-labels"><span>Invoice</span><span>Links</span><span>Credentials</span></div><div className="adaptive-note"><i>↗</i> Next round adapts to performance</div></div>
            <h3>Focus on what needs work</h3><p>Adaptive selection shifts practice toward the tactics where each learner can benefit most.</p>
          </article>
          <article className="landing-feature feature-insight">
            <div className="feature-number">03 <span>MEASURABLE PROGRESS</span></div>
            <div className="insight-preview"><div className="insight-preview-head"><span>TEAM SNAPSHOT</span><span>● LIVE VIEW</span></div><div className="insight-stat"><strong>Risk trends</strong><span>By completed round</span></div><svg viewBox="0 0 280 90" preserveAspectRatio="none" aria-hidden="true"><path d="M0 18 C36 22 42 40 80 35 S122 51 160 49 S205 69 240 62 S263 72 280 75" fill="none" stroke="#2b3741" strokeWidth="3" strokeLinecap="round"/><path d="M0 18 C36 22 42 40 80 35 S122 51 160 49 S205 69 240 62 S263 72 280 75" fill="none" stroke="#2b3741" strokeWidth="12" strokeOpacity=".06" strokeLinecap="round"/></svg><div className="insight-preview-foot"><span>LOWER RISK OVER TIME</span><b>View by department →</b></div></div>
            <h3>See the bigger picture</h3><p>Review organization trends and department patterns to guide the next training steps.</p>
          </article>
        </div>
      </section>
      <section className="landing-approach" id="approach">
        <div className="approach-copy"><span className="landing-overline">A SIMPLE, REPEATABLE LOOP</span><h2>Small moments.<br /><em>Stronger instincts.</em></h2><p>Each round gives employees a safe place to pause, decide, and learn. Admins get a clearer view of where the team needs support.</p><button className="approach-link" onClick={() => document.querySelector('.login-panel input')?.focus()}>Explore your workspace <span>↗</span></button></div>
        <div className="approach-steps"><div><span>01</span><section><b>Simulate</b><p>Present a realistic security decision in a safe environment.</p></section><i>↗</i></div><div><span>02</span><section><b>Coach</b><p>Give immediate, practical feedback based on the response.</p></section><i>✳</i></div><div><span>03</span><section><b>Improve</b><p>Adapt future practice and track progress across the team.</p></section><i>⌁</i></div></div>
      </section>
      <footer className="landing-footer"><Logo /><span>Build safer habits, one decision at a time.</span><a href="#signin" onClick={event => { event.preventDefault(); document.querySelector('.login-panel input')?.focus(); window.scrollTo({ top: 0, behavior: 'smooth' }) }}>Back to sign in ↑</a></footer>
    </main>
  )
}

function Shell({ user, children, onLogout, section = 'overview', onNavigate }) {
  const employee = user.role === 'employee'
  return (
    <div className="console">
      <aside className="side-nav">
        <Logo />
        <div className="tenant">
          <span className="tenant-avatar">{employee ? 'E' : 'A'}</span>
          <div>
            <b>{employee ? 'Employee workspace' : 'Safeguard Demo'}</b>
            <small>{employee ? 'Active Learner' : 'Admin Console'}</small>
          </div>
        </div>
        <nav>
          <span className="nav-section">WORKSPACE</span>
          <a href="#overview" className={section === 'overview' ? 'active' : ''} onClick={event => { event.preventDefault(); onNavigate('overview') }}>
            <i>▦</i><span>{employee ? 'My overview' : 'Risk Overview'}</span>
          </a>
          <a href="#assignments" className={section === 'assignments' ? 'active' : ''} onClick={event => { event.preventDefault(); onNavigate('assignments') }}>
            <i>◉</i><span>{employee ? 'My assignments' : 'Assignments'}</span>
          </a>
          {!employee && <a href="#reports" className={section === 'reports' ? 'active' : ''} onClick={event => { event.preventDefault(); onNavigate('reports') }}>
            <i>◫</i><span>Risk Analytics</span>
          </a>}
        </nav>
        <div className="nav-bottom">
          <div className="system-status">
            <span className="system-dot" />
            <span>AI Trainer Active</span>
          </div>
          <button onClick={onLogout}>Sign out →</button>
        </div>
      </aside>
      <main className="console-main">
        <header className="console-header">
          <div className="crumb">SAFEGUARD <b>/</b> {employee ? 'PERSONAL DEFENSE' : 'RISK OVERVIEW'}</div>
          <div className="header-tools">
            <div className="search-pill">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <circle cx="11" cy="11" r="8"></circle>
                <path d="m21 21-4.3-4.3"></path>
              </svg>
              <span>Search simulated tactics...</span>
              <kbd>⌘K</kbd>
            </div>
            <button className="icon-button" aria-label="Notifications">🔔</button>
            <span className="user-chip">{employee ? 'E' : 'A'}</span>
          </div>
        </header>
        {children}
      </main>
    </div>
  )
}

function Chart({ points = [], baseline = [] }) {
  if (!points.length) return <div className="empty-chart" style={{ padding: '30px', textAlign: 'center', color: 'var(--text-muted)' }}>No completed rounds yet. Your trend will appear as training progresses.</div>
  const width = 960, height = 320, padding = { top: 20, right: 28, bottom: 58, left: 64 }
  const plotWidth = width - padding.left - padding.right
  const plotHeight = height - padding.top - padding.bottom
  const xAt = index => padding.left + (index / Math.max(1, points.length - 1)) * plotWidth
  const yAt = risk => height - padding.bottom - Math.min(1, Math.max(0, risk)) * plotHeight
  const line = rows => rows.map((item, index) => {
    const x = padding.left + (index / Math.max(1, rows.length - 1)) * plotWidth
    const y = yAt(item.risk)
    return (index ? 'L' : 'M') + ' ' + x + ' ' + y
  }).join(' ')
  const tickCount = Math.min(5, points.length)
  const xTicks = Array.from({ length: tickCount }, (_, index) => {
    const pointIndex = Math.round(index * (points.length - 1) / Math.max(1, tickCount - 1))
    return { index: pointIndex, round: points[pointIndex]?.round ?? pointIndex + 1 }
  }).filter((tick, index, rows) => index === 0 || tick.index !== rows[index - 1].index)

  return (
    <svg className="risk-chart" viewBox={'0 0 ' + width + ' ' + height} role="img" aria-label="Organization risk score by training round, compared with the untargeted training baseline">
      <text className="chart-axis-title" x={padding.left} y={11}>RISK SCORE</text>
      {[0, .25, .5, .75, 1].map(value => {
        const y = height - padding.bottom - value * (height - padding.top - padding.bottom)
        return <g key={value}>
          <line x1={padding.left} x2={width - padding.right} y1={y} y2={y} />
          <text className="chart-tick" x={padding.left - 12} y={y + 4} textAnchor="end">{Math.round(value * 100)}%</text>
        </g>
      })}
      {xTicks.map(tick => <g key={tick.index}>
        <line className="chart-x-guide" x1={xAt(tick.index)} x2={xAt(tick.index)} y1={padding.top} y2={height - padding.bottom} />
        <text className="chart-tick" x={xAt(tick.index)} y={height - padding.bottom + 23} textAnchor="middle">{tick.round}</text>
      </g>)}
      <line className="chart-axis" x1={padding.left} x2={width - padding.right} y1={height - padding.bottom} y2={height - padding.bottom} />
      {baseline.length > 1 && <path className="baseline-line" d={line(baseline)} />}
      <path className="risk-line" d={line(points)} />
      {points.map((point, index) => <circle className="risk-point" key={point.round ?? index} cx={xAt(index)} cy={yAt(point.risk)} r={points.length < 16 ? 4 : 2.8}>
        <title>{'Round ' + (point.round ?? index + 1) + ': ' + Math.round(point.risk * 100) + '% risk'}</title>
      </circle>)}
      <text className="chart-x-title" x={(padding.left + width - padding.right) / 2} y={height - 8} textAnchor="middle">TRAINING ROUND</text>
    </svg>
  )
}

function Heatmap({ data = {}, tactics = [] }) {
  const departments = Object.keys(data)
  return (
    <div className="heatmap">
      <div className="heatmap-row heatmap-header">
        <span>Department</span>
        {tactics.map(tactic => <span key={tactic}>{tactic}</span>)}
      </div>
      {departments.length ? departments.map(department => (
        <div className="heatmap-row" key={department}>
          <b>{department}</b>
          {tactics.map(tactic => {
            const value = data[department]?.[tactic] || 0
            return (
              <span key={tactic} className="heat-cell" style={{ '--intensity': value }}>
                {Math.round(value * 100)}%
              </span>
            )
          })}
        </div>
      )) : <p className="muted-copy">Risk clustering is available once employees complete training rounds.</p>}
    </div>
  )
}

function Metric({ label, value, alert }) {
  return (
    <section className={'metric ' + (alert ? 'alert' : '')}>
      <span>{label}</span>
      <strong>{value}</strong>
    </section>
  )
}

function EmployeeDetail({ employee, onClose }) {
  const [data, setData] = useState(null)
  useEffect(() => { api('/admin/employees/' + employee.id).then(setData).catch(() => {}) }, [employee.id])
  return (
    <section className="page">
      <button className="back-link" onClick={onClose}>← Back to employee list</button>
      <div className="page-title">
        <div>
          <span>EMPLOYEE PROFILE</span>
          <h1>{employee.name}</h1>
          <p>{employee.department} · {employee.email}</p>
        </div>
        <button className="button button-secondary" onClick={() => download('csv', 'full', employee.id)}>Export CSV</button>
      </div>
      <section className="card">
        <div className="card-title">
          <div>
            <h2>Round history</h2>
            <p>Training decisions and safety scores.</p>
          </div>
        </div>
        <div className="detail-table">
          <div className="detail-row detail-label">
            <span>ROUND</span>
            <span>TACTIC</span>
            <span>RESPONSE</span>
            <span>SAFETY</span>
            <span>TIME</span>
          </div>
          {(data?.rounds || []).map(round => (
            <div className="detail-row" key={round.id}>
              <span>Round {round.round_number}</span>
              <span className="tactic-name">{round.tactic}</span>
              <span>{round.response}</span>
              <span>{Math.round((round.safety_score || 0) * 100)}%</span>
              <span>{round.response_time_seconds ? round.response_time_seconds.toFixed(1) + ' sec' : '—'}</span>
            </div>
          ))}
        </div>
      </section>
    </section>
  )
}

function AssignmentTab({ employees, assignments, reload }) {
  const [form, setForm] = useState({ employee_id: employees[0]?.id || '', title: 'Adaptive security awareness', total_rounds: 10 }),
        [message, setMessage] = useState(''),
        [analysis, setAnalysis] = useState(null)

  const viewAnalysis = async assignment => {
    try { setAnalysis(await api('/api/assignments/' + assignment.id + '/analysis')) }
    catch (err) { setMessage(err.message) }
  }

  const create = async event => {
    event.preventDefault()
    try {
      await api('/admin/training-assignments', {
        method: 'POST',
        body: JSON.stringify({ ...form, employee_id: Number(form.employee_id), total_rounds: Number(form.total_rounds) })
      })
      setMessage('Assignment created successfully.')
      reload()
    } catch (err) {
      setMessage(err.message)
    }
  }

  return (
    <section className="assignment-page">
      <section className="card">
        <div className="card-title">
          <div>
            <h2>Create training assignment</h2>
            <p>Deploy an adaptive simulation to an employee.</p>
          </div>
        </div>
        <form className="assignment-form" onSubmit={create}>
          <label>
            Employee
            <select value={form.employee_id} onChange={event => setForm({ ...form, employee_id: event.target.value })}>
              {employees.map(employee => <option key={employee.id} value={employee.id}>{employee.name}</option>)}
            </select>
          </label>
          <label>
            Assignment title
            <input value={form.title} onChange={event => setForm({ ...form, title: event.target.value })} />
          </label>
          <label>
            Rounds
            <input type="number" min="1" max="100" value={form.total_rounds} onChange={event => setForm({ ...form, total_rounds: event.target.value })} />
          </label>
          <button className="button button-primary">Create assignment</button>
        </form>
        {message && <p className="form-message">{message}</p>}
      </section>

      <section className="card">
        <div className="card-title">
          <div>
            <h2>Current assignments</h2>
            <p>Active and completed simulations.</p>
          </div>
          <button className="button button-secondary" onClick={() => download('pdf', 'full')}>Full report</button>
        </div>
        {assignments.map(assignment => (
          <div className="assignment-row" key={assignment.id}>
            <div>
              <b>{assignmentTitle(assignment.title)}</b>
              <p>{employees.find(employee => employee.id === assignment.employee_id)?.name || 'Employee'} · {assignment.completed_rounds}/{assignment.total_rounds} rounds</p>
            </div>
            <div className="assignment-actions"><span className={'status ' + assignment.status}>{assignment.status}</span><button className="row-link" onClick={() => viewAnalysis(assignment)}>View analysis</button></div>
          </div>
        ))}
        {analysis && <AssignmentAnalysis data={analysis} onClose={() => setAnalysis(null)} />}
      </section>
    </section>
  )
}

function AssignmentAnalysis({ data, onClose }) {
  const summary = data.analysis || {}
  return <div className="assignment-analysis-screen">
    <header className="analysis-header"><div><span>ASSIGNMENT ANALYSIS</span><h1>{assignmentTitle(data.assignment.title)}</h1><p>{data.assignment.completed_rounds} of {data.assignment.total_rounds} rounds completed</p></div><button className="button button-secondary" onClick={onClose}>← Back to assignments</button></header>
    <main className="analysis-content">
      <div className="analysis-status"><span className={'status ' + data.assignment.status}>{data.assignment.status}</span><span>{data.assignment.active_tactics?.join(' · ') || 'Adaptive training'}</span></div>
      <div className="analysis-grid"><Metric label="Average safety" value={summary.average_safety_score == null ? '—' : Math.round(summary.average_safety_score * 100) + '%'} /><Metric label="Detection reward" value={summary.average_detection_reward == null ? '—' : Math.round(summary.average_detection_reward * 100) + '%'} /><Metric label="Weakest tactic" value={summary.weakest_tactic || '—'} /></div>
      <section className="analysis-panel"><span>COACHING SUMMARY</span><h2>What to focus on next</h2><p>{summary.recommendation || 'Complete more rounds to generate a fuller analysis.'}</p></section>
      {summary.tactic_analysis && <section className="analysis-panel"><span>TACTIC BREAKDOWN</span><h2>Performance by tactic</h2><div className="tactic-breakdown">{Object.entries(summary.tactic_analysis).map(([tactic, item]) => <div className="tactic-breakdown-row" key={tactic}><b>{tactic}</b><span>{item.rounds} rounds</span><span>{Math.round((item.average_safety || 0) * 100)}% safety</span></div>)}</div></section>}
    </main>
  </div>
}

function AdminDashboard({ section = 'overview' }) {
  const [tab, setTab] = useState(section),
        [employees, setEmployees] = useState([]),
        [assignments, setAssignments] = useState([]),
        [overview, setOverview] = useState(null),
        [benchmark, setBenchmark] = useState(null),
        [modelHealth, setModelHealth] = useState(null),
        [selected, setSelected] = useState(null),
        [repeatOnly, setRepeatOnly] = useState(false),
        [error, setError] = useState('')

  const load = () => Promise.all([
    api('/admin/employees'),
    api('/admin/training-assignments'),
    api('/admin/analytics/overview'),
    api('/admin/analytics/sampling?rounds=20&repetitions=8')
  ]).then(([employeeRows, assignmentRows, overviewData, benchmarkData]) => {
    setEmployees(employeeRows)
    setAssignments(assignmentRows)
    setOverview(overviewData)
    setBenchmark(benchmarkData)
  }).catch(err => setError(err.message))

  useEffect(load, [])
  useEffect(() => {
    if (['overview', 'assignments', 'reports', 'model-health'].includes(section)) setTab(section)
  }, [section])
  useEffect(() => {
    if (tab === 'model-health') api('/api/classifier/info').then(setModelHealth).catch(err => setError(err.message))
  }, [tab])
  const baseline = useMemo(() => (benchmark?.rounds || []).map(row => ({ risk: 1 - row.random })), [benchmark]),
        visibleEmployees = employees.filter(employee => !repeatOnly || employee.repeat_clicker)

  if (selected) return <EmployeeDetail employee={selected} onClose={() => setSelected(null)} />

  return (
    <section className="page assignments-workspace">
      <div className="page-title">
        <div>
          <span>SECURITY POSTURE</span>
          <h1>Risk overview</h1>
          <p>Monitor workforce susceptibility and evaluate adaptive AI training.</p>
        </div>
        <div className="title-actions">
          <button className="button button-secondary" onClick={() => download('csv')}>Export CSV</button>
          <button className="button button-primary" onClick={() => download('pdf', 'executive')}>Executive Report</button>
        </div>
      </div>

      {error && <p className="form-error">{error}</p>}

      <div className="sub-tabs">
        <button className={tab === 'overview' ? 'active' : ''} onClick={() => setTab('overview')}>Overview</button>
        <button className={tab === 'assignments' ? 'active' : ''} onClick={() => setTab('assignments')}>
          Assignments <b>{assignments.length}</b>
        </button>
        <button className={tab === 'model-health' ? 'active' : ''} onClick={() => setTab('model-health')}>Model Health</button>
      </div>

      {tab === 'employees' ? (
        <section className="page"><div className="page-title"><div><span>TEAM MANAGEMENT</span><h1>Employees</h1><p>Review learner activity and open an employee risk profile.</p></div></div><section className="card employee-card"><div className="employee-table">{employees.map(employee => <div className="employee-row" key={employee.id}><span className="employee-name"><i>{employee.name[0]}</i><b>{employee.name}</b></span><span>{employee.department}</span><span>{employee.rounds} rounds</span><button className="row-link" onClick={() => setSelected(employee)}>View</button></div>)}</div></section></section>
      ) : tab === 'settings' ? (
        <section className="page"><div className="page-title"><div><span>WORKSPACE SETTINGS</span><h1>Settings</h1><p>Configure training and review workspace defaults.</p></div></div><section className="card"><h2>Training configuration</h2><p>Active tactics and assignment controls are managed from the Assignments workspace. Model diagnostics are available in Model Health.</p><button className="button button-primary" onClick={() => setTab('assignments')}>Open assignments</button></section></section>
      ) : tab === 'model-health' ? (
        <section className="card model-health-card">
          <div className="card-title"><div><h2>Classifier diagnostics</h2><p>Admin-only health metrics for the behavior model.</p></div><span className="status active">{modelHealth?.status || 'Loading'}</span></div>
          <div className="metric-grid">
            <Metric label="Accuracy" value={modelHealth?.accuracy == null ? '—' : Math.round(modelHealth.accuracy * 100) + '%'} />
            <Metric label="Macro F1" value={modelHealth?.macro_f1 == null ? '—' : modelHealth.macro_f1.toFixed(3)} />
            <Metric label="Training samples" value={modelHealth?.n_train ?? '—'} />
            <Metric label="Test samples" value={modelHealth?.n_test ?? '—'} />
          </div>
          <h3>Confusion matrix</h3>
          <p className="muted">Rows are actual responses; columns are predicted responses: {modelHealth?.classes?.join(', ') || '—'}.</p>
          <pre className="confusion-matrix">{modelHealth ? JSON.stringify(modelHealth.confusion_matrix, null, 2) : 'Loading…'}</pre>
        </section>
      ) : tab === 'reports' ? (
        <section className="page">
          <div className="page-title"><div><span>RISK ANALYTICS</span><h1>Training analytics</h1><p>Review organization trends and exportable security reports.</p></div><button className="button button-primary" onClick={() => download('pdf', 'executive')}>Export report</button></div>
          <section className="card"><div className="card-title"><div><h2>Risk trend</h2><p>Adaptive training performance over completed rounds.</p></div></div><Chart points={overview?.trend || []} baseline={baseline} /></section>
          <div className="metric-grid"><Metric label="Rounds analyzed" value={overview?.rounds_analyzed ?? 0} /><Metric label="Organization risk" value={(overview?.organization_risk_score ?? 0) + '/100'} /><Metric label="Repeat clickers" value={overview?.repeat_clickers ?? 0} alert /></div>
        </section>
      ) : tab === 'overview' ? (
        <>
          <section className="score-strip">
            <div>
              <span>ORGANIZATION RISK SCORE</span>
              <strong>{overview?.organization_risk_score ?? 0}<small>/100</small></strong>
              <p className={overview?.risk_change <= 0 ? 'improving' : 'worsening'}>
                {overview?.risk_change <= 0 ? '↓' : '↑'} {Math.abs(overview?.risk_change || 0)} points <em>vs. previous period</em>
              </p>
            </div>
            <div className="score-explainer">
              <b>Adaptive Thompson Sampling</b>
              <p>Phishing simulations automatically adjust to probe and strengthen your team's most vulnerable tactics.</p>
            </div>
          </section>

          <div className="metric-grid">
            <Metric label="Employees" value={overview?.total_employees ?? 0} />
            <Metric label="Rounds analyzed" value={overview?.rounds_analyzed ?? 0} />
            <Metric label="Avg. time to report" value={overview?.avg_time_to_report ? overview.avg_time_to_report + 's' : '—'} />
            <Metric label="Repeat clickers" value={overview?.repeat_clickers ?? 0} alert />
          </div>

          <section className="card">
            <div className="card-title">
              <div>
                <h2>Is risk going up or down?</h2>
                <p>This line shows how employee risk changes after each training round.</p>
              </div>
              <div className="chart-key">
                <span><i className="risk-legend" />Your team's risk</span>
                <span><i className="baseline-legend" />Untargeted baseline</span>
              </div>
            </div>
            <Chart points={overview?.trend || []} baseline={baseline} />
            <p className="chart-caption">Risk is shown from 0% to 100%. Lower scores indicate safer responses; the dashed red line is a simulated untargeted baseline.</p>
          </section>

          <div className="two-column">
            <section className="card">
              <div className="card-title">
                <div>
                  <h2>Department risk</h2>
                  <p>Susceptibility clusters by phishing tactic.</p>
                </div>
                <span className="legend-low">Low → High risk</span>
              </div>
              <Heatmap data={overview?.heatmap} tactics={overview?.active_tactics || []} />
            </section>

            <section className="card">
              <div className="card-title">
                <div>
                  <h2>Training Insights</h2>
                  <p>Targeted recommendations.</p>
                </div>
              </div>
              <div className="insight">
                <span>01</span>
                <div>
                  <b>Adaptive Learning Advantage</b>
                  <p>Our multi-armed bandit focuses rounds on employee blindspots, accelerating instinctive reporting.</p>
                </div>
              </div>
              <div className="insight">
                <span>02</span>
                <div>
                  <b>Prioritize Repeat Clickers</b>
                  <p>Direct follow-up suggested for staff repeatedly submitting credentials or clicking unrecognized links.</p>
                </div>
              </div>
            </section>
          </div>

          <section className="card employee-card">
            <div className="card-title">
              <div>
                <h2>Employees</h2>
                <p>Learner engagement and risk distribution.</p>
              </div>
              <button className={repeatOnly ? 'filter-button selected' : 'filter-button'} onClick={() => setRepeatOnly(!repeatOnly)}>
                ⚑ Repeat clickers only
              </button>
            </div>
            <div className="employee-table">
              <div className="employee-row employee-header">
                <span>EMPLOYEE</span>
                <span>DEPARTMENT</span>
                <span>RISK</span>
                <span>ROUNDS</span>
                <span />
              </div>
              {visibleEmployees.map(employee => (
                <div className="employee-row" key={employee.id}>
                  <span className="employee-name">
                    <i>{employee.name[0]}</i>
                    <b>{employee.name}</b>
                    {employee.repeat_clicker && <em>Repeat</em>}
                  </span>
                  <span>{employee.department}</span>
                  <span>
                    <u className={employee.risk_score > .6 ? 'risk-high' : employee.risk_score > .3 ? 'risk-medium' : 'risk-low'}>
                      {Math.round(employee.risk_score * 100)}%
                    </u>
                  </span>
                  <span>{employee.rounds}</span>
                  <button className="row-link" onClick={() => setSelected(employee)}>View</button>
                </div>
              ))}
              {!visibleEmployees.length && <p className="empty-table">No repeat clickers are currently detected.</p>}
            </div>
          </section>
        </>
      ) : (
        <AssignmentTab employees={employees} assignments={assignments} reload={load} />
      )}
    </section>
  )
}

function EmployeeDashboard({ onTrain, section = 'overview' }) {
  const [assignments, setAssignments] = useState([]),
        [analytics, setAnalytics] = useState(null),
        [assignmentLoading, setAssignmentLoading] = useState(true),
        [assignmentError, setAssignmentError] = useState(''),
        [assignmentAnalysis, setAssignmentAnalysis] = useState(null)

  const viewAssignmentAnalysis = async assignment => {
    try { setAssignmentAnalysis(await api('/api/assignments/' + assignment.id + '/analysis')) }
    catch (err) { setAssignmentError(err.message) }
  }

  useEffect(() => {
    let cancelled = false
    setAssignmentLoading(true)
    setAssignmentError('')
    Promise.all([api('/employee/assignments'), api('/employee/analytics/personal')])
      .then(([assignmentRows, analyticsData]) => {
        if (cancelled) return
        setAssignments(Array.isArray(assignmentRows) ? assignmentRows : [])
        setAnalytics(analyticsData)
      }).catch(err => { if (!cancelled) setAssignmentError(err.message) })
      .finally(() => { if (!cancelled) setAssignmentLoading(false) })
    return () => { cancelled = true }
  }, [])

  const openAssignments = () => (
    <section className="page assignments-workspace">
      <div className="page-title">
        <div>
          <span>TRAINING ASSIGNMENTS</span>
          <h1>My assignments</h1>
          <p>Start or continue your personalized simulations.</p>
        </div>
      </div>
      {assignmentError && <p className="form-error">{assignmentError}</p>}
      {assignmentLoading ? <section className="card loading-state">Loading your assignments…</section> : assignments.length === 0 ? (
        <section className="card empty-state">
          <h2>No assignments yet</h2>
          <p>Your administrator has not assigned a training simulation to you yet. Once one is assigned, it will appear here.</p>
        </section>
      ) : assignments.map(item => (
        <section className="card assignment-row" key={item.id}>
          <div>
            <b>{assignmentTitle(item.title)}</b>
            <p>{item.completed_rounds} of {item.total_rounds} rounds completed · <span className={'status ' + item.status}>{item.status}</span></p>
          </div>
          {['scheduled','active'].includes(item.status) && (
            <div className="assignment-actions"><button className="row-link" onClick={() => viewAssignmentAnalysis(item)}>View analysis</button><button className="button button-primary" onClick={() => onTrain(item)}>Continue</button></div>
          )}
          {item.status === 'completed' && <button className="row-link" onClick={() => viewAssignmentAnalysis(item)}>View analysis</button>}
        </section>
      ))}
      {assignmentAnalysis && <AssignmentAnalysis data={assignmentAnalysis} onClose={() => setAssignmentAnalysis(null)} />}
    </section>
  )

  if (section === 'assignments') return openAssignments()
  if (section === 'reports') return (
    <section className="page">
      <div className="page-title">
        <div>
          <span>TRAINING REPORTS</span>
          <h1>My reports</h1>
          <p>Review previous scenario decisions and feedback.</p>
        </div>
      </div>
      <section className="card">
        <div className="detail-table">
          {(analytics?.history || []).map(item => (
            <div className="detail-row" key={item.id}>
              <span>Round {item.round_number}</span>
              <span className="tactic-name">{item.tactic}</span>
              <span>{item.response}</span>
              <span>{Math.round((item.safety_score || 0) * 100)}% safety</span>
            </div>
          ))}
        </div>
      </section>
    </section>
  )

  const active = assignments.find(item => ['scheduled', 'active'].includes(item.status))

  return (
    <section className="page">
      <div className="page-title">
        <div>
          <span>PERSONAL SECURITY POSTURE</span>
          <h1>My security progress</h1>
          <p>Sharpen your phishing detection instincts with adaptive practice.</p>
        </div>
      </div>

      <section className="personal-score">
        <div>
          <span>PERSONAL RISK SCORE</span>
          <strong>{analytics?.risk_score ?? 0}<small>/100</small></strong>
          <p>Safer than <b>{analytics?.percentile ?? 0}%</b> of your organization.</p>
        </div>
        <div className="personal-score-chart">
          <p className="chart-caption">This shows your risk after each training round. A lower line means you are becoming safer.</p>
          <Chart points={analytics?.trend || []} />
        </div>
      </section>

      <div className="personal-cards">
        <section className="card">
          <span>STRONGEST INSTINCT</span>
          <h2>{analytics?.strongest_tactic || '—'}</h2>
          <p>You consistently spot and report this tactic.</p>
        </section>
        <section className="card">
          <span>PRACTICE TARGET</span>
          <h2>{analytics?.weakest_tactic || '—'}</h2>
          <p>Focus here during upcoming simulations.</p>
        </section>
      </div>

      {active ? (
        <section className="training-callout">
          <div>
            <span>ACTIVE SIMULATION</span>
            <h2>{active.title}</h2>
            <p>{active.completed_rounds} of {active.total_rounds} rounds completed.</p>
          </div>
          <button className="button button-primary" onClick={() => onTrain(active)}>Continue simulation</button>
        </section>
      ) : (
        <section className="card">
          <div className="card-title">
            <div>
              <h2>Recent activity</h2>
              <p>Your simulation response history.</p>
            </div>
          </div>
          <div className="detail-table">
            {(analytics?.history || []).map(item => (
              <div className="detail-row" key={item.id}>
                <span className="tactic-name">{item.tactic}</span>
                <span>{item.response}</span>
                <span>{Math.round((item.safety_score || 0) * 100)}% safety</span>
                <span>{item.response_time_seconds ? item.response_time_seconds.toFixed(1) + ' sec' : '—'}</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </section>
  )
}

function TrainingWorkspace({ assignment, onExit }) {
  const [round, setRound] = useState(null),
        [feedback, setFeedback] = useState(null),
        [busy, setBusy] = useState(true),
        [finished, setFinished] = useState(false),
        [error, setError] = useState('')
  const submitting = useRef(false)

  const next = async () => {
    setBusy(true)
    setError('')
    try {
      setRound(await api('/employee/assignments/' + assignment.id + '/start', { method: 'POST' }))
      setFeedback(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => { next() }, [])

  const respond = async response => {
    if (!round || busy || submitting.current) return
    submitting.current = true
    setBusy(true)
    setError('')
    try {
      const result = await api('/employee/round/' + round.id + '/respond', { method: 'POST', body: JSON.stringify({ response }) })
      const currentAssignments = await api('/employee/assignments')
      if (currentAssignments.find(item => item.id === assignment.id)?.status === 'completed') {
        setFinished(true)
      } else {
        setFeedback({
          text: result.feedback_text || 'Response recorded.',
          indicators: result.feedback_indicators || [],
          risk: Math.max(0, Math.min(1, 1 - (result.classifier_score ?? result.safety_score ?? 0.5)))
        })
      }
    } catch (err) {
      setError(err.message)
    } finally {
      submitting.current = false
      setBusy(false)
    }
  }

  if (finished) return (
    <main className="training-page">
      <section className="completion-card">
        <span>✓</span>
        <h1>Simulation complete</h1>
        <p>Your responses have been processed and fed into your personal defense model.</p>
        <button className="button button-primary" onClick={onExit}>Return to workspace</button>
      </section>
    </main>
  )

  return (
    <main className="training-page">
      <header className="training-header">
        <Logo />
        <span>SIMULATION ENVIRONMENT</span>
        <button className="back-link" onClick={onExit}>Exit simulation</button>
      </header>
      <section className="training-content">
        {error && <p className="form-error">{error}</p>}
        {busy && !round ? (
          <div className="loading-state">Synthesizing personalized training scenario…</div>
        ) : feedback ? (
          <section className="feedback-card">
            <span>ROUND EVALUATION</span>
            <h1>Security Takeaway</h1>
            <div className={'risk-badge risk-' + (feedback.risk < 0.6 ? 'low' : feedback.risk <= 0.8 ? 'medium' : 'high')}>
              {feedback.risk < 0.6 ? 'LOW' : feedback.risk <= 0.8 ? 'MEDIUM' : 'HIGH'} RISK
            </div>
            <small className="risk-threshold-caption">Low &lt; 0.6 · Medium 0.6–0.8 · High &gt; 0.8</small>
            <p>{feedback.text}</p>
            {feedback.indicators?.length > 0 && (
              <details className="why-matters">
                <summary>Why this matters</summary>
                <div>
                  {feedback.indicators.map((item, index) => (
                    <article key={item.id || index}>
                      <b>{item.title || 'Documented phishing indicator'}</b>
                      <small>{item.source || 'Security reference'}</small>
                      <p>{item.snippet || item.text}</p>
                    </article>
                  ))}
                </div>
              </details>
            )}
            <button className="button button-primary" onClick={next}>Continue to next round</button>
          </section>
        ) : (
          <>
            <div className="round-meta">
              <span>ROUND {round?.round_number} OF {assignment.total_rounds}</span>
              <span className="tactic-name">{round?.tactic_selected}</span>
            </div>
            <article className="email-card">
              <div className="email-top">
                <h1>{round?.scenario?.subject}</h1>
                <span>{round?.scenario?.source === 'groq' ? 'AI generated' : 'Template scenario'}</span>
              </div>
              <div className="sender">
                <i>{round?.scenario?.sender_name?.[0]}</i>
                <div>
                  <b>{round?.scenario?.sender_name}</b>
                  <small>{round?.scenario?.sender_email} · to me</small>
                </div>
              </div>
              <p>{round?.scenario?.body}</p>
            </article>
            <footer className="decision-bar">
              <b>What is your response to this message?</b>
              <div>
                <button className="decision safe" disabled={busy} onClick={() => respond('report')}>Report Phishing</button>
                <button className="decision" disabled={busy} onClick={() => respond('ignore')}>Ignore</button>
                <button className="decision danger" disabled={busy} onClick={() => respond('click')}>Open Link</button>
                <button className="decision danger" disabled={busy} onClick={() => respond('credentials')}>Submit Credentials</button>
              </div>
            </footer>
          </>
        )}
      </section>
    </main>
  )
}

function App() {
  const [user, setUser] = useState(null),
        [training, setTraining] = useState(null),
        [section, setSection] = useState('overview')

  if (!user) return <Login onLogin={userData => { setUser(userData); setSection('overview') }} />
  if (training) return <TrainingWorkspace assignment={training} onExit={() => setTraining(null)} />

  return (
    <Shell user={user} section={section} onNavigate={setSection} onLogout={() => { window.__token = null; setUser(null) }}>
      {user.role === 'employee' ? <EmployeeDashboard section={section} onTrain={setTraining} /> : <AdminDashboard section={section} />}
    </Shell>
  )
}

createRoot(document.getElementById('root')).render(<App />)


