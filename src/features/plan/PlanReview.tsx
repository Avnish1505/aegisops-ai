import { Link } from '@tanstack/react-router'
import { useDecision, useIntake, useLabels } from '../../api/queries'
import { candidateQuotes } from '../../lib/candidate'
import { Mono, Notice, Panel } from '../../components/ui/Panel'
import { PlanStatus } from '../../components/ui/SeverityGlyph'
import { istClock, istDate } from '../../lib/time'
import { ActionBar } from './ActionBar'
import { AssignmentsTable } from './AssignmentsTable'
import { BaselineDiff } from './BaselineDiff'
import { ConstraintList } from './ConstraintList'
import { EvidencePanel, type QuotesByIncident } from './EvidencePanel'
import { SitrepDraft } from './SitrepDraft'
import { VerifierChecklist } from './VerifierChecklist'

export function PlanReview({ decisionId }: { decisionId: number }) {
  const decision = useDecision(decisionId)
  const labels = useLabels(decision.data?.scenario).data
  // Incidents confirmed in triage carry the model's quotes; seeded exercise injects have none.
  const intake = useIntake(false).data ?? []
  const quotes: QuotesByIncident = Object.fromEntries(
    intake.filter((report) => report.incident_id).map((report) => [report.incident_id as string, candidateQuotes(report.candidate)]),
  )

  if (decision.isPending) return <p className="p-6 text-muted">Loading plan {decisionId}…</p>
  if (decision.isError) return <div className="p-6"><Notice tone="high">Plan {decisionId}: {decision.error.message}</Notice></div>
  const plan = decision.data
  const created = new Date(plan.created_at.endsWith('Z') || plan.created_at.includes('+') ? plan.created_at : `${plan.created_at}Z`)

  return (
    <div className="flex h-full flex-col">
      <div className="min-h-0 flex-1 overflow-auto">
        <header className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-divider bg-surface px-4 py-2">
          <h1 className="text-lg font-semibold">
            Plan <span className="font-mono">{plan.decision_id}</span>
          </h1>
          {plan.approvals.length > 0 ? (
            <span className="text-sm font-semibold">
              {plan.approvals[plan.approvals.length - 1].action === 'approve' ? 'Approved' : 'Rejected'} by{' '}
              {plan.approvals[plan.approvals.length - 1].actor}
            </span>
          ) : (
            <PlanStatus status={plan.status} />
          )}
          <span className="text-sm text-muted">
            {plan.scenario.incidents.length} incidents · {plan.assignments.length} assignments · coverage{' '}
            <span className="font-mono text-text">{Math.round(plan.coverage * 100)}%</span>
          </span>
          <span className="text-sm text-muted">
            Proposed by <span className="text-text">{plan.proposer_sub ?? 'unknown'}</span> · {istDate(created)} {istClock(created)} ·{' '}
            engine <Mono>{plan.engine}</Mono>
          </span>
          <span className="text-sm text-muted">
            Travel times <Mono>{plan.travel_times.provider}</Mono>
          </span>
          <Link to="/audit/$decisionId" params={{ decisionId: plan.decision_id }} className="ml-auto text-sm underline">
            Audit trail
          </Link>
        </header>
        {plan.travel_times.degraded && (
          <div className="px-4 pt-2">
            <Notice tone="high">Degraded travel times: {plan.travel_times.degraded_reason}</Notice>
          </div>
        )}
        <div className="grid grid-cols-1 gap-3 p-3 xl:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
          <div className="space-y-3">
            <Panel title="Assignments" labelledBy="assignments-title">
              <AssignmentsTable plan={plan} labels={labels} />
            </Panel>
            <Panel title="Constraints" labelledBy="constraints-title">
              <ConstraintList plan={plan} labels={labels} />
            </Panel>
            <Panel title="Difference from the unconstrained plan" labelledBy="baseline-title">
              <BaselineDiff plan={plan} labels={labels} />
            </Panel>
          </div>
          <div className="space-y-3">
            <Panel title={`Verifier · ${plan.verification.verdict === 'blocked' ? 'BLOCKED' : 'pass'}`} labelledBy="verifier-title">
              <VerifierChecklist report={plan.verification} />
            </Panel>
            <Panel title="SITREP draft" labelledBy="sitrep-title">
              <SitrepDraft plan={plan} />
            </Panel>
            <Panel title="Evidence" labelledBy="evidence-title">
              <EvidencePanel plan={plan} labels={labels} quotes={quotes} />
            </Panel>
          </div>
        </div>
      </div>
      <ActionBar plan={plan} />
    </div>
  )
}
