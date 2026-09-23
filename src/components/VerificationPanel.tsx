import type { CheckResult, Decision } from '../types'
import { humanize } from '../lib/format'
import { Panel } from './Panel'
import { StatusBadge } from './StatusBadge'

const severityOrder: Record<CheckResult['severity'], number> = { critical: 0, high: 1, warning: 2 }

/** Every deterministic check the verifier ran on this plan. Failures come first:
 * a critical failure is why a plan is blocked, so it must be the first thing read. */
export function VerificationPanel({ decision }: { decision: Decision }) {
  const report = decision.verification
  const checks = [...report.checks].sort(
    (a, b) => Number(a.passed) - Number(b.passed) || severityOrder[a.severity] - severityOrder[b.severity],
  )
  const failed = checks.filter((check) => !check.passed).length
  const sitrep = decision.drafts.find((draft) => draft.kind === 'sitrep')

  return (
    <Panel>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="panel-heading">Verification</h3>
          <p className="mt-1 text-xs text-ink-500">
            {checks.length} deterministic checks against {decision.travel_provider ?? 'unknown'} travel times
            {report.safety_gate_blocked ? ' · safety gate: critical demand unmet' : ''}.
          </p>
        </div>
        <StatusBadge tone={report.verdict === 'pass' ? 'positive' : 'blocked'}>
          {report.verdict === 'pass' ? `Verified · ${failed} flagged` : `Blocked · ${failed} failed`}
        </StatusBadge>
      </div>
      <ul className="mt-3 divide-y divide-ink-200 border-y border-ink-200">
        {checks.map((check) => (
          <li key={check.id} className="flex gap-3 py-2 text-xs">
            <span
              aria-label={check.passed ? 'passed' : 'failed'}
              className={`mt-0.5 font-mono font-bold ${check.passed ? 'text-status-available' : check.severity === 'critical' ? 'text-status-blocked' : 'text-sev-medium'}`}
            >
              {check.passed ? 'PASS' : 'FAIL'}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <span className="font-semibold text-ink-900">{humanize(check.id)}</span>
                <span className="font-bold uppercase tracking-wide text-ink-500">{check.severity}</span>
              </div>
              <p className="mt-0.5 break-words leading-5 text-ink-700">{check.message}</p>
            </div>
          </li>
        ))}
      </ul>
      {sitrep && (
        <details className="mt-3">
          <summary className="cursor-pointer text-xs font-semibold text-ink-700">Situation report (numbers verified)</summary>
          <pre className="mt-2 overflow-x-auto whitespace-pre-wrap bg-paper-sunken p-3 font-mono text-[11px] leading-5 text-ink-800">
            {sitrep.text}
          </pre>
        </details>
      )}
    </Panel>
  )
}
