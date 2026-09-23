import { useState } from 'react'
import { submitDisposition } from '../api'
import type { Assignment, Decision, DispositionResult } from '../types'
import { humanize, shortId } from '../lib/format'
import { Panel } from './Panel'
import { SectionHeader } from './SectionHeader'
import { StatusBadge } from './StatusBadge'
import { VerificationPanel } from './VerificationPanel'
import { ActionButton, SecondaryButton } from './buttons'

interface ResultsPanelProps {
  decision: Decision
  onActiveAssignment: (assignment: Assignment | null) => void
}

/** The decision-review surface. This is the safety-critical part of the
 * product: it must always distinguish an advisory recommendation (ready for
 * human review) from a blocked allocation (escalation required), and must
 * never imply resources are dispatched automatically. */
export function ResultsPanel({ decision, onActiveAssignment }: ResultsPanelProps) {
  const [pinnedAssignment, setPinnedAssignment] = useState<Assignment | null>(null)
  const [disposition, setDisposition] = useState<DispositionResult | null>(null)
  const [reason, setReason] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const isBlocked = decision.status === 'blocked'
  const coverage = Math.round(decision.coverage * 100)

  const setActive = (assignment: Assignment | null) => onActiveAssignment(assignment ?? pinnedAssignment)
  const isPinned = (assignment: Assignment) =>
    pinnedAssignment?.incident_id === assignment.incident_id && pinnedAssignment.resource_id === assignment.resource_id
  const pinAssignment = (assignment: Assignment) => {
    const next = isPinned(assignment) ? null : assignment
    setPinnedAssignment(next)
    onActiveAssignment(next)
  }

  const recordDisposition = async (action: 'approve' | 'reject') => {
    if (!reason.trim()) {
      setSubmitError('Enter a reason before recording a disposition.')
      return
    }
    setSubmitError(null)
    setIsSubmitting(true)
    try {
      setDisposition(await submitDisposition(decision.decision_id, action, reason.trim()))
    } catch (caught) {
      setSubmitError(caught instanceof Error ? caught.message : 'Could not record the disposition.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <section className="space-y-4" aria-live="polite">
      <div className={`border p-4 ${isBlocked ? 'border-status-blocked/40 bg-status-blocked/10' : 'border-accent-700/30 bg-accent-100/50'}`}>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className={`status-dot ${isBlocked ? 'animate-pulse bg-status-blocked' : 'bg-accent-700'}`} />
              <p className={`text-xs font-bold uppercase tracking-[0.14em] ${isBlocked ? 'text-status-blocked' : 'text-accent-700'}`}>
                {isBlocked ? 'Allocation blocked — escalation required' : 'Recommendation ready for review'}
              </p>
            </div>
            <h2 className="mt-2 text-lg font-semibold text-ink-900">Advisory — human approval required</h2>
            <p className="mt-1 max-w-2xl text-sm text-ink-600">
              {isBlocked
                ? 'A critical capability is unmet. This is not an automated dispatch state; an operator must assess and escalate.'
                : 'The baseline engine produced a proposed allocation. No resources are dispatched by this interface.'}
            </p>
          </div>
          <StatusBadge tone={isBlocked ? 'blocked' : 'review'}>{isBlocked ? 'Blocked' : 'Human gate'}</StatusBadge>
        </div>
      </div>

      {decision.unmet_requirements.length > 0 && (
        <div className="border-l-4 border-sev-medium bg-sev-medium/10 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-bold text-sev-medium">Safety-relevant capability gaps</p>
              <p className="mt-0.5 text-xs text-ink-600">Unmet requirements need operator assessment before any action.</p>
            </div>
            <span className="rounded bg-sev-medium/15 px-2 py-1 text-xs font-bold text-sev-medium">
              {decision.unmet_requirements.length} unmet
            </span>
          </div>
          <div className="mt-3 grid gap-2 md:grid-cols-2">
            {decision.unmet_requirements.map((requirement) => (
              <div
                key={`${requirement.incident_id}-${requirement.resource_type}`}
                className="flex items-center justify-between border border-sev-medium/25 bg-paper-raised px-3 py-2 text-xs"
              >
                <span className="font-mono text-ink-700">{shortId(requirement.incident_id)}</span>
                <span className="text-ink-700">
                  {requirement.quantity} × {humanize(requirement.resource_type)}{' '}
                  <span className="ml-1 uppercase text-sev-medium">{requirement.severity}</span>
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <Panel padded={false} className="overflow-hidden">
        <div className="border-b border-ink-200 px-4 py-3">
          <SectionHeader
            as="h3"
            title="Proposed assignments"
            description="Hover or select a row to trace its line on the grid."
            meta={<span className="font-mono text-xs text-ink-500">{decision.assignments.length} routes</span>}
          />
        </div>
        {decision.assignments.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-paper-sunken text-[10px] uppercase tracking-wider text-ink-500">
                <tr>
                  <th className="px-4 py-2.5 font-semibold">Incident</th>
                  <th className="px-4 py-2.5 font-semibold">Resource</th>
                  <th className="px-4 py-2.5 font-semibold">Travel</th>
                </tr>
              </thead>
              <tbody>
                {decision.assignments.map((assignment) => {
                  const pinned = isPinned(assignment)
                  return (
                    <tr
                      key={`${assignment.incident_id}-${assignment.resource_id}`}
                      tabIndex={0}
                      onMouseEnter={() => setActive(assignment)}
                      onMouseLeave={() => setActive(null)}
                      onFocus={() => setActive(assignment)}
                      onBlur={() => setActive(null)}
                      onClick={() => pinAssignment(assignment)}
                      className={`cursor-pointer border-t border-ink-200 transition-colors ${pinned ? 'bg-accent-100/70' : 'hover:bg-ink-100 focus:bg-ink-100'}`}
                    >
                      <td className="px-4 py-3 font-mono text-accent-700">{shortId(assignment.incident_id)}</td>
                      <td className="px-4 py-3">
                        <span className="text-ink-800">{shortId(assignment.resource_id)}</span>
                        <span className="ml-2 text-ink-500">{humanize(assignment.resource_type)}</span>
                      </td>
                      <td className="px-4 py-3 font-mono text-ink-700">{assignment.travel_minutes.toFixed(1)} min</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="px-4 py-5 text-sm text-ink-500">No allocation routes were produced.</p>
        )}
      </Panel>

      <div className="grid gap-4 xl:grid-cols-[0.85fr_1.15fr]">
        <Panel>
          <div className="flex items-center justify-between">
            <div>
              <h3 className="panel-heading">Coverage</h3>
              <p className="mt-1 text-xs text-ink-500">Share of required units assigned, not outcome probability.</p>
            </div>
            <span className="font-mono text-2xl font-semibold text-ink-900">{coverage}%</span>
          </div>
          <div className="mt-4 h-2 overflow-hidden bg-ink-200">
            <div className={`h-full transition-all ${isBlocked ? 'bg-status-blocked' : 'bg-accent-700'}`} style={{ width: `${coverage}%` }} />
          </div>
        </Panel>
        <Panel>
          <h3 className="panel-heading">Safety findings</h3>
          <div className="mt-3 space-y-2">
            {decision.safety_findings.length ? (
              decision.safety_findings.map((finding, index) => (
                <div
                  key={`${finding.code}-${index}`}
                  className={`border-l-2 px-3 py-2 text-xs ${finding.severity === 'critical' ? 'border-status-blocked bg-status-blocked/10' : 'border-sev-medium bg-sev-medium/10'}`}
                >
                  <div className="flex justify-between gap-3">
                    <span className={`font-bold uppercase tracking-wide ${finding.severity === 'critical' ? 'text-status-blocked' : 'text-sev-medium'}`}>
                      {finding.code}
                    </span>
                    <span className={`font-bold uppercase ${finding.severity === 'critical' ? 'text-status-blocked' : 'text-sev-medium'}`}>
                      {finding.severity}
                    </span>
                  </div>
                  {finding.incident_id && <span className="mt-1 block font-mono text-ink-500">{shortId(finding.incident_id)}</span>}
                  <p className="mt-1 leading-5 text-ink-700">{finding.message}</p>
                </div>
              ))
            ) : (
              <p className="text-sm text-ink-500">No safety findings returned by the engine.</p>
            )}
          </div>
        </Panel>
      </div>

      <VerificationPanel decision={decision} />

      <Panel>
        <div className="flex items-center justify-between">
          <div>
            <h3 className="panel-heading">Decision trace</h3>
            <p className="mt-1 text-xs text-ink-500">Explainability log from {decision.engine}.</p>
          </div>
          <span className="font-mono text-[10px] text-ink-500">{decision.decision_trace.length} steps</span>
        </div>
        <ol className="mt-4 space-y-0 border-l border-ink-300 pl-5">
          {decision.decision_trace.map((step, index) => (
            <li key={`${step}-${index}`} className="relative pb-4 last:pb-0">
              <span className="absolute -left-[1.82rem] top-0 flex h-4 w-4 items-center justify-center rounded-full border border-ink-300 bg-paper-raised font-mono text-[9px] text-ink-600">
                {index + 1}
              </span>
              <p className="text-sm leading-6 text-ink-700">{step}</p>
            </li>
          ))}
        </ol>
      </Panel>

      <div className="border border-accent-700/25 bg-accent-100/40 p-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="text-sm font-semibold text-ink-900">Operator disposition</p>
            <p className="mt-0.5 text-xs text-ink-500">
              {disposition
                ? 'Recorded to the decision audit log.'
                : 'Recorded to the decision audit log once submitted — this does not dispatch resources.'}
            </p>
          </div>
          {disposition ? (
            <StatusBadge tone={disposition.action === 'approve' ? 'positive' : 'negative'}>
              {disposition.action === 'approve' ? 'Approved by operator' : 'Rejected by operator'}
              {' · '}
              {new Date(disposition.timestamp).toLocaleString()}
            </StatusBadge>
          ) : (
            <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:items-start">
              <div>
                <label className="sr-only" htmlFor="disposition-reason">Reason for this disposition</label>
                <input
                  id="disposition-reason"
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  placeholder="Reason for this disposition (required)"
                  disabled={isSubmitting}
                  className="w-full border border-ink-300 bg-paper-sunken px-3 py-2 text-sm text-ink-800 placeholder:text-ink-400 sm:w-64"
                />
              </div>
              <div className="flex gap-2">
                <SecondaryButton tone="negative" disabled={isSubmitting} onClick={() => void recordDisposition('reject')}>
                  Reject
                </SecondaryButton>
                <ActionButton
                  disabled={isBlocked}
                  loading={isSubmitting}
                  onClick={() => void recordDisposition('approve')}
                  title={isBlocked ? 'Blocked decisions cannot be approved — escalate to a human reviewer instead.' : undefined}
                >
                  Approve recommendation
                </ActionButton>
              </div>
            </div>
          )}
        </div>
        {isBlocked && !disposition && (
          <p className="mt-2 text-xs text-status-blocked">
            Blocked decisions cannot be approved — escalate to a human reviewer instead. Rejection is still recorded.
          </p>
        )}
        {submitError && <p role="alert" className="mt-2 text-xs text-status-blocked">{submitError}</p>}
      </div>
    </section>
  )
}
