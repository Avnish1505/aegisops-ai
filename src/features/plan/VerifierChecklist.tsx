import type { CheckResult, VerificationReport } from '../../types'

const ORDER = { critical: 0, high: 1, warning: 2 }

function Check({ check }: { check: CheckResult }) {
  const tone = check.passed ? 'text-muted' : check.severity === 'critical' ? 'text-critical' : 'text-high'
  return (
    <li className="flex gap-2 border-b border-divider px-3 py-1 text-sm">
      <span aria-hidden="true" className={`w-3 shrink-0 font-semibold ${tone}`}>{check.passed ? '✓' : check.severity === 'critical' ? '◆' : '▲'}</span>
      <div className="min-w-0">
        <div className={check.passed ? '' : `font-semibold ${tone}`}>
          <span className="sr-only">{check.passed ? 'Passed' : `Failed, ${check.severity}`}: </span>
          <span className="font-mono text-xs text-muted">{check.id}</span> {check.message}
        </div>
      </div>
    </li>
  )
}

export function VerifierChecklist({ report }: { report: VerificationReport }) {
  const failed = report.checks.filter((c) => !c.passed).sort((a, b) => ORDER[a.severity] - ORDER[b.severity])
  const passed = report.checks.filter((c) => c.passed)
  return (
    <div>
      <h3 className="px-3 pt-2 text-sm font-semibold">
        Failed <span className="font-mono">{failed.length}</span>
      </h3>
      {failed.length === 0 ? <p className="px-3 py-1 text-sm text-muted">No check failed.</p> : <ul>{failed.map((c) => <Check key={c.id} check={c} />)}</ul>}
      {report.safety_gate_blocked && (
        <p className="px-3 py-1 text-sm font-semibold text-blocked">Safety gate: a critical incident has declared unmet demand.</p>
      )}
      <details className="mt-1">
        <summary className="cursor-pointer px-3 py-1 text-sm font-semibold">
          Passed <span className="font-mono">{passed.length}</span>
        </summary>
        <ul>{passed.map((c) => <Check key={c.id} check={c} />)}</ul>
      </details>
    </div>
  )
}
