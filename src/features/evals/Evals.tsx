import { useQuery } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { Mono, Notice, Panel } from '../../components/ui/Panel'
import { api } from '../../lib/http'

interface Estimate {
  value: number | null
  ci95: [number | null, number | null]
  n: number
}
interface ReportFile {
  file: string
  data: Record<string, unknown>
}
interface Reports {
  fault_injection: ReportFile | null
  eval: ReportFile | null
  llm_vs_solver: ReportFile | null
  user_study: ReportFile | null
  superseded: { file: string; note: string }[]
}

function isEstimate(value: unknown): value is Estimate {
  return typeof value === 'object' && value !== null && 'value' in value && 'ci95' in value
}

/** "72.0% [65.1, 78.3] (n = 200)"; n/a when there was nothing to measure. */
export function formatEstimate(estimate: Estimate, percent = true, digits = 1): string {
  if (estimate.value === null) return 'n/a'
  const scale = percent ? 100 : 1
  const unit = percent ? '%' : ''
  const [low, high] = estimate.ci95
  const interval = low === null || high === null ? '' : ` [${(low * scale).toFixed(digits)}, ${(high * scale).toFixed(digits)}]`
  return `${(estimate.value * scale).toFixed(digits)}${unit}${interval} (n = ${estimate.n})`
}

function NotRun({ what, how }: { what: string; how: ReactNode }) {
  return (
    <div className="space-y-1 p-3 text-sm">
      <p className="font-semibold">Not run yet.</p>
      <p className="text-muted">{what}</p>
      <p className="text-muted">{how}</p>
    </div>
  )
}

function Source({ file }: { file: string }) {
  return <p className="px-3 pb-2 text-xs text-muted">Source: <Mono>{file}</Mono></p>
}

function MetricTable({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <table className="w-full text-sm">
      <tbody>
        {rows.map(([label, value]) => (
          <tr key={label} className="border-b border-divider">
            <th scope="row" className="py-1 pl-3 text-left font-normal text-muted">{label}</th>
            <td className="py-1 pr-3 text-right font-mono">{value}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function FaultInjection({ report }: { report: ReportFile }) {
  const d = report.data as {
    classes_caught: number; classes: number; faults_caught: number; faults: number
    clean_false_blocks: number; clean_scenarios: number
    per_class: { name: string; expected_check: string; severity: string; caught: number; blocked: number; scenarios: number }[]
  }
  return (
    <>
      <MetricTable
        rows={[
          ['Fault classes caught on every scenario', `${d.classes_caught}/${d.classes}`],
          ['Injected faults caught', `${d.faults_caught}/${d.faults}`],
          ['Clean solver plans falsely blocked', `${d.clean_false_blocks}/${d.clean_scenarios}`],
        ]}
      />
      <details className="px-3 py-2">
        <summary className="cursor-pointer text-sm font-medium">Per class</summary>
        <table className="mt-1 w-full text-sm">
          <thead className="text-left text-muted">
            <tr><th className="font-medium">Class</th><th className="font-medium">Check</th><th className="font-medium">Severity</th><th className="text-right font-medium">Caught</th><th className="text-right font-medium">Blocked</th></tr>
          </thead>
          <tbody>
            {d.per_class.map((row) => (
              <tr key={row.name} className="border-b border-divider">
                <td>{row.name}</td><td><Mono>{row.expected_check}</Mono></td><td>{row.severity}</td>
                <td className="text-right font-mono">{row.caught}/{row.scenarios}</td>
                <td className="text-right font-mono">{row.blocked}/{row.scenarios}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
      <p className="px-3 pb-1 text-xs text-muted">Faults are injected one at a time by mutators written alongside the verifier; this is not an adversarial evaluation of a live model.</p>
      <Source file={report.file} />
    </>
  )
}

/** Renders any report's top-level estimates generically so a new metric shows up without code. */
function Estimates({ data, prefix = '' }: { data: Record<string, unknown>; prefix?: string }) {
  const rows: [string, ReactNode][] = []
  const walk = (value: unknown, path: string) => {
    if (isEstimate(value)) {
      const percent = !/latency|km|per_plan|cost|objective/.test(path)
      rows.push([path.replace(/_/g, ' '), formatEstimate(value, percent, percent ? 1 : 2)])
    } else if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
      for (const [key, child] of Object.entries(value)) walk(child, path ? `${path} · ${key}` : key)
    }
  }
  walk(data, prefix)
  return rows.length ? <MetricTable rows={rows} /> : <p className="p-3 text-sm text-muted">No estimates in this report.</p>
}

export function Evals() {
  const reports = useQuery({ queryKey: ['reports'], queryFn: () => api<Reports>('/api/v1/reports', { auth: false }) })
  if (reports.isPending) return <p className="p-6 text-muted">Loading reports…</p>
  if (reports.isError) return <div className="p-6"><Notice tone="high">{reports.error.message}</Notice></div>
  const r = reports.data
  return (
    <div className="h-full overflow-auto">
      <header className="border-b border-divider bg-surface px-4 py-2">
        <h1 className="text-lg font-semibold">Evaluations</h1>
        <p className="text-sm text-muted">Only committed results are shown, each with its source file. 95% intervals are bootstrap intervals from the report.</p>
      </header>
      <div className="grid grid-cols-1 gap-3 p-3 xl:grid-cols-2">
        <Panel title="Verifier fault injection" labelledBy="fi-title">
          {r.fault_injection ? <FaultInjection report={r.fault_injection} /> : <NotRun what="No fault report found." how={<>Run <Mono>python scripts/fault_report.py</Mono>.</>} />}
        </Panel>
        <Panel title="LLM steps (read, constraints, SITREP, end to end)" labelledBy="eval-title">
          {r.eval ? (
            <>
              <Estimates data={r.eval.data} />
              <Source file={r.eval.file} />
            </>
          ) : (
            <NotRun what="No live-model evaluation has been committed, so no accuracy, latency or cost is claimed." how={<>With a key: <Mono>python -m evals.run</Mono>.</>} />
          )}
        </Panel>
        <Panel title="LLM-direct allocation vs CP-SAT" labelledBy="lvs-title">
          {r.llm_vs_solver ? (
            <>
              <Estimates data={(r.llm_vs_solver.data.summary as Record<string, unknown>) ?? {}} />
              <Source file={r.llm_vs_solver.file} />
            </>
          ) : (
            <NotRun what="The 100-scenario comparison on OSRM road times has not been run against a model." how={<>With a key: <Mono>python -m evals.llm_vs_solver</Mono>.</>} />
          )}
        </Panel>
        <Panel title="User study" labelledBy="study-title">
          {r.user_study ? (
            <>
              <Estimates data={r.user_study.data} />
              <Source file={r.user_study.file} />
            </>
          ) : (
            <NotRun what="No study sessions have been analysed." how="The study protocol is part of milestone M4." />
          )}
        </Panel>
      </div>
      {r.superseded.length > 0 && (
        <section className="px-3 pb-3">
          <h2 className="text-sm font-semibold">Superseded reports</h2>
          <ul className="text-sm text-muted">
            {r.superseded.map((s) => (
              <li key={s.file}><Mono>{s.file}</Mono>: {s.note}</li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
