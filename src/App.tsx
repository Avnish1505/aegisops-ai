import { useMemo, useState } from 'react'
import { fetchDecision, fetchScenario } from './api'
import type { Assignment, Decision, Incident, Resource, Scenario, Severity } from './types'

type SelectedEntity =
  | { kind: 'incident'; entity: Incident }
  | { kind: 'resource'; entity: Resource }
  | null
type Approval = 'approved' | 'rejected' | null

const severityStyle: Record<Severity, { label: string; fill: string; text: string }> = {
  low: { label: 'Low', fill: '#60a5fa', text: 'text-blue-300' },
  medium: { label: 'Medium', fill: '#facc15', text: 'text-yellow-300' },
  high: { label: 'High', fill: '#fb923c', text: 'text-orange-300' },
  critical: { label: 'Critical', fill: '#f43f5e', text: 'text-rose-300' },
}

const humanize = (value: string) => value.replace(/_/g, ' ')
const shortId = (id: string) => (id.length > 13 ? `${id.slice(0, 13)}…` : id)

function SeverityBadge({ severity }: { severity: Severity }) {
  const style = severityStyle[severity]
  return (
    <span className={`inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider ${style.text}`}>
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: style.fill }} />
      {style.label}
    </span>
  )
}

function Grid({
  scenario,
  decision,
  selected,
  activeAssignment,
  onSelect,
}: {
  scenario: Scenario
  decision: Decision | null
  selected: SelectedEntity
  activeAssignment: Assignment | null
  onSelect: (entity: SelectedEntity) => void
}) {
  const incidentsById = useMemo(() => new Map(scenario.incidents.map((item) => [item.id, item])), [scenario])
  const resourcesById = useMemo(() => new Map(scenario.resources.map((item) => [item.id, item])), [scenario])
  const activeKey = activeAssignment ? `${activeAssignment.incident_id}:${activeAssignment.resource_id}` : null
  const point = ([x, y]: [number, number]) => ({ x, y: 100 - y })
  const isSelected = (kind: 'incident' | 'resource', id: string) => selected?.kind === kind && selected.entity.id === id
  const keyboardSelect = (event: React.KeyboardEvent<SVGGElement>, entity: SelectedEntity) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onSelect(entity)
    }
  }

  return (
    <div className="relative overflow-hidden border border-slate-700/80 bg-[#081522]">
      <svg viewBox="-7 -7 114 114" className="block aspect-[1.28/1] w-full" aria-label="Synthetic scenario coordinate grid">
        <defs>
          <pattern id="minorGrid" width="10" height="10" patternUnits="userSpaceOnUse">
            <path d="M 10 0 L 0 0 0 10" fill="none" stroke="#334155" strokeWidth="0.22" opacity="0.9" />
          </pattern>
          <filter id="criticalGlow" x="-100%" y="-100%" width="300%" height="300%">
            <feGaussianBlur stdDeviation="1.4" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>
        <rect x="0" y="0" width="100" height="100" fill="url(#minorGrid)" />
        <rect x="0" y="0" width="100" height="100" fill="none" stroke="#64748b" strokeWidth="0.4" />
        {[0, 20, 40, 60, 80, 100].map((tick) => (
          <g key={tick} fill="#64748b" fontSize="3" fontFamily="ui-monospace, SFMono-Regular, monospace">
            <text x={tick} y="105" textAnchor="middle">{tick}</text>
            <text x="-3" y={100 - tick + 1} textAnchor="end">{tick}</text>
          </g>
        ))}

        {decision?.assignments.map((assignment) => {
          const incident = incidentsById.get(assignment.incident_id)
          const resource = resourcesById.get(assignment.resource_id)
          if (!incident || !resource) return null
          const from = point(incident.location)
          const to = point(resource.location)
          const isActive = activeKey === `${assignment.incident_id}:${assignment.resource_id}`
          return (
            <line
              key={`${assignment.incident_id}-${assignment.resource_id}`}
              x1={from.x} y1={from.y} x2={to.x} y2={to.y}
              stroke={isActive ? '#f8fafc' : '#38bdf8'}
              strokeWidth={isActive ? 1.25 : 0.38}
              opacity={isActive ? 1 : activeAssignment ? 0.18 : 0.5}
              className="transition-all duration-150"
            />
          )
        })}

        {scenario.resources.map((resource) => {
          const { x, y } = point(resource.location)
          const selectedResource = isSelected('resource', resource.id)
          return (
            <g
              key={resource.id}
              role="button"
              tabIndex={0}
              aria-label={`Resource ${resource.id}: ${humanize(resource.type)}, ${resource.available ? 'available' : 'unavailable'}`}
              className="cursor-pointer"
              onClick={() => onSelect({ kind: 'resource', entity: resource })}
              onKeyDown={(event) => keyboardSelect(event, { kind: 'resource', entity: resource })}
            >
              {selectedResource && <circle cx={x} cy={y} r="5" fill="none" stroke="#f8fafc" strokeWidth="0.5" />}
              <rect x={x - 2.1} y={y - 2.1} width="4.2" height="4.2" rx="0.4" fill={resource.available ? '#22d3ee' : '#475569'} stroke="#0f172a" strokeWidth="0.7" opacity={resource.available ? 1 : 0.45} />
              <path d={`M ${x - 1.05} ${y} H ${x + 1.05} M ${x} ${y - 1.05} V ${y + 1.05}`} stroke="#082f49" strokeWidth="0.45" opacity={resource.available ? 1 : 0.6} />
            </g>
          )
        })}

        {scenario.incidents.map((incident) => {
          const { x, y } = point(incident.location)
          const selectedIncident = isSelected('incident', incident.id)
          const style = severityStyle[incident.severity]
          return (
            <g
              key={incident.id}
              role="button"
              tabIndex={0}
              aria-label={`Incident ${incident.id}: ${humanize(incident.type)}, ${incident.severity} severity`}
              className="cursor-pointer"
              onClick={() => onSelect({ kind: 'incident', entity: incident })}
              onKeyDown={(event) => keyboardSelect(event, { kind: 'incident', entity: incident })}
            >
              {incident.severity === 'critical' && <circle cx={x} cy={y} r="5.2" fill="none" stroke="#f43f5e" strokeWidth="0.55" className="animate-beacon origin-center" />}
              {selectedIncident && <circle cx={x} cy={y} r="5" fill="none" stroke="#f8fafc" strokeWidth="0.55" />}
              {incident.severity === 'critical' ? (
                <path d={`M ${x} ${y - 3.2} L ${x + 3.2} ${y} L ${x} ${y + 3.2} L ${x - 3.2} ${y} Z`} fill={style.fill} stroke="#fff1f2" strokeWidth="0.5" filter="url(#criticalGlow)" />
              ) : incident.severity === 'high' ? (
                <path d={`M ${x} ${y - 3} L ${x + 3} ${y + 2.3} L ${x - 3} ${y + 2.3} Z`} fill={style.fill} stroke="#fff7ed" strokeWidth="0.45" />
              ) : (
                <circle cx={x} cy={y} r={incident.severity === 'medium' ? '2.7' : '2.25'} fill={style.fill} stroke="#0f172a" strokeWidth="0.6" />
              )}
            </g>
          )
        })}
      </svg>
      <div className="absolute bottom-3 left-3 flex flex-wrap gap-x-4 gap-y-1 rounded border border-slate-700 bg-slate-950/85 px-2.5 py-1.5 text-[10px] text-slate-300 backdrop-blur">
        <span><span className="mr-1 inline-block h-2 w-2 rotate-45 bg-rose-500" />Critical</span>
        <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-orange-400" />High</span>
        <span><span className="mr-1 inline-block h-2 w-2 rounded-full bg-yellow-400" />Medium</span>
        <span><span className="mr-1 inline-block h-2 w-2 bg-cyan-400" />Resource</span>
      </div>
    </div>
  )
}

function DetailPanel({ selected }: { selected: SelectedEntity }) {
  if (!selected) {
    return <div className="flex min-h-[185px] items-center border border-dashed border-slate-700 px-4 text-sm leading-6 text-slate-500">Select an incident or resource marker to inspect its operational details.</div>
  }
  if (selected.kind === 'incident') {
    const item = selected.entity
    const location = `${item.location[0].toFixed(1)}, ${item.location[1].toFixed(1)}`
    return (
      <div className="space-y-4">
        <div className="flex items-start justify-between gap-3"><div><p className="font-mono text-xs text-sky-300">{item.id}</p><p className="mt-1 text-sm font-semibold capitalize text-slate-100">{humanize(item.type)}</p></div><SeverityBadge severity={item.severity} /></div>
        <dl className="grid grid-cols-2 gap-x-3 gap-y-3 border-t border-slate-800 pt-3 text-xs"><div><dt className="metric-label">Grid coordinate</dt><dd className="mt-1 font-mono text-slate-200">{location}</dd></div><div><dt className="metric-label">Reported</dt><dd className="mt-1 text-slate-200">T+{item.reported_at_min} min</dd></div><div><dt className="metric-label">People affected</dt><dd className="mt-1 text-lg font-semibold text-slate-100">{item.people_affected}</dd></div><div><dt className="metric-label">Needs</dt><dd className="mt-1 space-y-0.5 text-slate-200">{Object.entries(item.resources_needed).map(([type, count]) => <div key={type}>{count} × {humanize(type)}</div>)}</dd></div></dl>
      </div>
    )
  }
  const item = selected.entity
  const location = `${item.location[0].toFixed(1)}, ${item.location[1].toFixed(1)}`
  return (
    <div className="space-y-4"><div className="flex items-start justify-between gap-3"><div><p className="font-mono text-xs text-cyan-300">{item.id}</p><p className="mt-1 text-sm font-semibold capitalize text-slate-100">{humanize(item.type)}</p></div><span className={`rounded px-2 py-1 text-[10px] font-bold uppercase tracking-wider ${item.available ? 'bg-emerald-500/15 text-emerald-300' : 'bg-slate-700 text-slate-400'}`}>{item.available ? 'Available' : 'Unavailable'}</span></div><dl className="grid grid-cols-2 gap-x-3 gap-y-3 border-t border-slate-800 pt-3 text-xs"><div><dt className="metric-label">Grid coordinate</dt><dd className="mt-1 font-mono text-slate-200">{location}</dd></div><div><dt className="metric-label">ETA speed</dt><dd className="mt-1 text-slate-200">{item.eta_speed.toFixed(1)} units/min</dd></div></dl></div>
  )
}

function ResultsPanel({ decision, onActiveAssignment }: { decision: Decision; onActiveAssignment: (assignment: Assignment | null) => void }) {
  const [pinnedAssignment, setPinnedAssignment] = useState<Assignment | null>(null)
  const [approval, setApproval] = useState<Approval>(null)
  const isBlocked = decision.status === 'blocked'
  const confidence = Math.round(decision.advisory_confidence * 100)
  const setActive = (assignment: Assignment | null) => onActiveAssignment(assignment ?? pinnedAssignment)
  const pinAssignment = (assignment: Assignment) => {
    const next = pinnedAssignment?.incident_id === assignment.incident_id && pinnedAssignment.resource_id === assignment.resource_id ? null : assignment
    setPinnedAssignment(next)
    onActiveAssignment(next)
  }
  return (
    <section className="space-y-4" aria-live="polite">
      <div className={`border p-4 ${isBlocked ? 'border-rose-500/70 bg-rose-950/60' : 'border-emerald-500/50 bg-emerald-950/35'}`}>
        <div className="flex items-start justify-between gap-5"><div><div className="flex items-center gap-2"><span className={`status-dot ${isBlocked ? 'animate-pulse bg-rose-400' : 'bg-emerald-400'}`} /><p className={`text-xs font-bold uppercase tracking-[0.14em] ${isBlocked ? 'text-rose-300' : 'text-emerald-300'}`}>{isBlocked ? 'Allocation blocked — escalation required' : 'Recommendation ready for review'}</p></div><h2 className="mt-2 text-lg font-semibold text-white">Advisory — human approval required</h2><p className="mt-1 max-w-2xl text-sm text-slate-300">{isBlocked ? 'A critical capability is unmet. This is not an automated dispatch state; an operator must assess and escalate.' : 'The baseline engine produced a proposed allocation. No resources are dispatched by this interface.'}</p></div><span className={`shrink-0 border px-2 py-1 font-mono text-[10px] uppercase ${isBlocked ? 'border-rose-400/50 text-rose-200' : 'border-emerald-400/40 text-emerald-200'}`}>{isBlocked ? 'BLOCKED' : 'HUMAN GATE'}</span></div>
      </div>

      {decision.unmet_requirements.length > 0 && <div className="border-l-4 border-amber-400 bg-amber-400/10 p-4"><div className="flex items-center justify-between"><div><p className="text-sm font-bold text-amber-200">Safety-relevant capability gaps</p><p className="mt-0.5 text-xs text-amber-100/75">Unmet requirements need operator assessment before any action.</p></div><span className="rounded bg-amber-400/15 px-2 py-1 text-xs font-bold text-amber-200">{decision.unmet_requirements.length} UNMET</span></div><div className="mt-3 grid gap-2 md:grid-cols-2">{decision.unmet_requirements.map((requirement) => <div key={`${requirement.incident_id}-${requirement.resource_type}`} className="flex items-center justify-between border border-amber-300/20 bg-slate-950/20 px-3 py-2 text-xs"><span className="font-mono text-slate-300">{shortId(requirement.incident_id)}</span><span className="text-amber-100">{requirement.quantity} × {humanize(requirement.resource_type)} <span className="ml-1 uppercase text-amber-300">{requirement.severity}</span></span></div>)}</div></div>}

      <div className="panel overflow-hidden"><div className="flex items-center justify-between border-b border-slate-800 px-4 py-3"><div><p className="panel-heading">Proposed assignments</p><p className="mt-0.5 text-xs text-slate-500">Hover or select a row to trace its line on the grid.</p></div><span className="font-mono text-xs text-slate-400">{decision.assignments.length} routes</span></div>{decision.assignments.length ? <div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead className="bg-slate-950/60 text-[10px] uppercase tracking-wider text-slate-500"><tr><th className="px-4 py-2.5 font-semibold">Incident</th><th className="px-4 py-2.5 font-semibold">Resource</th><th className="px-4 py-2.5 font-semibold">Travel</th></tr></thead><tbody>{decision.assignments.map((assignment) => { const pinned = pinnedAssignment?.incident_id === assignment.incident_id && pinnedAssignment.resource_id === assignment.resource_id; return <tr key={`${assignment.incident_id}-${assignment.resource_id}`} tabIndex={0} onMouseEnter={() => setActive(assignment)} onMouseLeave={() => setActive(null)} onFocus={() => setActive(assignment)} onBlur={() => setActive(null)} onClick={() => pinAssignment(assignment)} className={`cursor-pointer border-t border-slate-800 transition-colors ${pinned ? 'bg-sky-400/15' : 'hover:bg-slate-800/75 focus:bg-slate-800/75'}`}><td className="px-4 py-3 font-mono text-sky-200">{shortId(assignment.incident_id)}</td><td className="px-4 py-3"><span className="text-slate-200">{shortId(assignment.resource_id)}</span><span className="ml-2 text-slate-500">{humanize(assignment.resource_type)}</span></td><td className="px-4 py-3 font-mono text-slate-200">{assignment.travel_minutes.toFixed(1)} min</td></tr> })}</tbody></table></div> : <p className="px-4 py-5 text-sm text-slate-500">No allocation routes were produced.</p>}</div>

      <div className="grid gap-4 xl:grid-cols-[0.85fr_1.15fr]">
        <div className="panel p-4"><div className="flex items-center justify-between"><div><p className="panel-heading">Advisory confidence</p><p className="mt-1 text-xs text-slate-500">Allocation coverage, not outcome probability.</p></div><span className="font-mono text-2xl font-semibold text-slate-100">{confidence}%</span></div><div className="mt-4 h-2 overflow-hidden bg-slate-800"><div className={`h-full transition-all ${isBlocked ? 'bg-rose-500' : 'bg-cyan-400'}`} style={{ width: `${confidence}%` }} /></div></div>
        <div className="panel p-4"><p className="panel-heading">Safety findings</p><div className="mt-3 space-y-2">{decision.safety_findings.length ? decision.safety_findings.map((finding, index) => <div key={`${finding.code}-${index}`} className={`border-l-2 px-3 py-2 text-xs ${finding.severity === 'critical' ? 'border-rose-400 bg-rose-500/10' : 'border-amber-400 bg-amber-500/10'}`}><div className="flex justify-between gap-3"><span className={`font-bold uppercase tracking-wide ${finding.severity === 'critical' ? 'text-rose-300' : 'text-amber-300'}`}>{finding.code}</span><span className={`font-bold uppercase ${finding.severity === 'critical' ? 'text-rose-200' : 'text-amber-200'}`}>{finding.severity}</span></div>{finding.incident_id && <span className="mt-1 block font-mono text-slate-500">{shortId(finding.incident_id)}</span>}<p className="mt-1 leading-5 text-slate-300">{finding.message}</p></div>) : <p className="text-sm text-slate-500">No safety findings returned by the engine.</p>}</div></div>
      </div>

      <div className="panel p-4"><div className="flex items-center justify-between"><div><p className="panel-heading">Decision trace</p><p className="mt-1 text-xs text-slate-500">Explainability log from {decision.engine}.</p></div><span className="font-mono text-[10px] text-slate-500">{decision.decision_trace.length} steps</span></div><ol className="mt-4 space-y-0 border-l border-slate-700 pl-5">{decision.decision_trace.map((step, index) => <li key={`${step}-${index}`} className="relative pb-4 last:pb-0"><span className="absolute -left-[1.82rem] top-0 flex h-4 w-4 items-center justify-center rounded-full border border-slate-600 bg-slate-900 font-mono text-[9px] text-slate-300">{index + 1}</span><p className="text-sm leading-6 text-slate-300">{step}</p></li>)}</ol></div>

      <div className="border border-sky-400/25 bg-sky-400/[0.07] p-4"><div className="flex flex-wrap items-center justify-between gap-4"><div><p className="text-sm font-semibold text-sky-100">Operator disposition</p><p className="mt-0.5 text-xs text-slate-400">Local interface state only — not persisted to the backend.</p></div>{approval ? <span className={`rounded border px-3 py-2 text-xs font-bold uppercase tracking-wider ${approval === 'approved' ? 'border-emerald-400/60 bg-emerald-400/10 text-emerald-200' : 'border-rose-400/60 bg-rose-400/10 text-rose-200'}`}>{approval === 'approved' ? 'Approved by operator' : 'Rejected by operator'}</span> : <div className="flex gap-2"><button onClick={() => setApproval('rejected')} className="border border-rose-400/60 px-3 py-2 text-xs font-bold text-rose-200 transition hover:bg-rose-400/10">Reject</button><button onClick={() => setApproval('approved')} className="bg-emerald-400 px-3 py-2 text-xs font-bold text-slate-950 transition hover:bg-emerald-300">Approve recommendation</button></div>}</div>{/* Phase 2 placeholder: send the operator's signed approval/rejection to a persistent backend endpoint. */}</div>
    </section>
  )
}

function App() {
  const [seedText, setSeedText] = useState('42')
  const [scenario, setScenario] = useState<Scenario | null>(null)
  const [decision, setDecision] = useState<Decision | null>(null)
  const [selected, setSelected] = useState<SelectedEntity>(null)
  const [activeAssignment, setActiveAssignment] = useState<Assignment | null>(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const [isRecommending, setIsRecommending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const generateScenario = async () => {
    const normalized = seedText.trim()
    const seed = normalized === '' ? undefined : Number(normalized)
    if (seed !== undefined && (!Number.isSafeInteger(seed) || seed < 0)) {
      setError('Seed must be a whole non-negative number, or leave it blank for a random synthetic scenario.')
      return
    }
    setIsGenerating(true); setError(null)
    try {
      const next = await fetchScenario(seed)
      setScenario(next); setDecision(null); setSelected(null); setActiveAssignment(null)
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not generate a scenario.')
    } finally { setIsGenerating(false) }
  }
  const getRecommendation = async () => {
    if (!scenario) return
    setIsRecommending(true); setError(null); setActiveAssignment(null); setDecision(null)
    try { setDecision(await fetchDecision(scenario)) } catch (caught) { setError(caught instanceof Error ? caught.message : 'Could not retrieve a recommendation.') } finally { setIsRecommending(false) }
  }

  return <main className="min-h-screen bg-[#07111f] text-slate-100"><header className="border-b border-slate-800 bg-[#091421]"><div className="mx-auto flex max-w-[1600px] items-center justify-between px-6 py-4"><div className="flex items-center gap-3"><div className="flex h-8 w-8 items-center justify-center border border-cyan-400/60 bg-cyan-400/10 font-mono text-sm font-bold text-cyan-300">A</div><div><h1 className="text-base font-semibold tracking-tight">AegisOps <span className="text-slate-500">AI</span></h1><p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Synthetic crisis decision support</p></div></div><div className="flex items-center gap-2 text-xs text-slate-400"><span className="status-dot bg-cyan-400" />Research environment <span className="mx-1 text-slate-700">/</span> No automated dispatch</div></div></header>
    <div className="mx-auto max-w-[1600px] px-6 py-6"><section className="panel mb-5 flex items-center justify-between gap-6 p-4"><div><p className="eyebrow">Scenario control</p><p className="mt-1 text-sm text-slate-300">Generate reproducible, synthetic incidents on a 0–100 coordinate grid.</p></div><div className="flex items-center gap-2"><label className="sr-only" htmlFor="seed">Scenario seed</label><input id="seed" value={seedText} onChange={(event) => setSeedText(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void generateScenario() }} inputMode="numeric" placeholder="Random seed" className="w-32 border border-slate-600 bg-slate-950 px-3 py-2 text-sm font-mono text-slate-100 placeholder:text-slate-600" /><button onClick={() => void generateScenario()} disabled={isGenerating} className="bg-cyan-400 px-3 py-2 text-sm font-bold text-slate-950 transition hover:bg-cyan-300 disabled:cursor-wait disabled:opacity-60">{isGenerating ? 'Generating…' : 'Generate scenario'}</button></div></section>
    {error && <div role="alert" className="mb-5 flex items-start justify-between gap-4 border border-rose-400/50 bg-rose-950/45 p-4"><div><p className="text-sm font-semibold text-rose-200">API connection or validation error</p><p className="mt-1 text-sm text-rose-100/85">{error}</p></div><button onClick={() => setError(null)} className="text-xs font-bold text-rose-200 underline underline-offset-4">Dismiss</button></div>}
    {!scenario ? <section className="flex min-h-[500px] items-center justify-center border border-dashed border-slate-700 bg-slate-900/30"><div className="max-w-md text-center"><p className="eyebrow">Awaiting synthetic scenario</p><h2 className="mt-3 text-xl font-semibold">Start with seed 42</h2><p className="mt-2 text-sm leading-6 text-slate-400">Generate a scenario to inspect incidents, available capabilities, and an operator-gated allocation advisory.</p></div></section> : <><div className="mb-4 flex items-center justify-between"><div><p className="eyebrow">Active scenario</p><p className="mt-1 font-mono text-sm text-sky-200">{scenario.scenario_id} <span className="ml-2 font-sans text-slate-500">{scenario.incidents.length} incidents · {scenario.resources.length} resources</span></p></div><button onClick={() => void getRecommendation()} disabled={isRecommending} className="border border-cyan-300 bg-cyan-400/10 px-4 py-2 text-sm font-bold text-cyan-200 transition hover:bg-cyan-400 hover:text-slate-950 disabled:cursor-wait disabled:opacity-60">{isRecommending ? 'Analyzing scenario…' : 'Get recommendation'}</button></div><div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_330px]"><section className="panel p-4"><div className="mb-3 flex items-center justify-between"><div><p className="panel-heading">Operational coordinate plane</p><p className="mt-0.5 text-xs text-slate-500">Synthetic grid only — not geographic location data.</p></div><span className="font-mono text-[10px] text-slate-500">X 0–100 / Y 0–100</span></div><Grid scenario={scenario} decision={decision} selected={selected} activeAssignment={activeAssignment} onSelect={setSelected} /></section><aside className="panel self-start p-4"><p className="eyebrow">Marker inspection</p><h2 className="mt-1 mb-4 panel-heading">Entity details</h2><DetailPanel selected={selected} /></aside></div>{isRecommending && <div className="mt-5 border border-cyan-400/30 bg-cyan-400/[0.06] p-4 text-sm text-cyan-100"><span className="mr-2 inline-block h-2 w-2 animate-pulse rounded-full bg-cyan-300" />Requesting advisory from the rule-based baseline engine. No action is being taken.</div>}{decision && <div className="mt-5"><ResultsPanel decision={decision} onActiveAssignment={setActiveAssignment} /></div>}</>}</div></main>
}

export default App
