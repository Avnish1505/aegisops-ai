import { useNavigate } from '@tanstack/react-router'
import { useState } from 'react'
import { usePlan, useTranslate } from '../../api/queries'
import type { Labels, StoredDecision } from '../../api/types'
import { Button, Mono, Notice } from '../../components/ui/Panel'
import { QuotedText } from '../../components/ui/QuotedText'
import { useIdentity } from '../../lib/auth'
import type { ConstraintProposal } from '../../types'
import { describeConstraint } from './constraints'

export function ConstraintList({ plan, labels }: { plan: StoredDecision; labels: Labels | undefined }) {
  return (
    <div className="space-y-2 p-3">
      {plan.constraints.length === 0 && <p className="text-sm text-muted">No constraints: this is the solver's unconstrained plan.</p>}
      <ol className="space-y-2">
        {plan.constraints.map((constraint, index) => {
          const source = plan.constraint_sources[index]
          return (
            <li key={index} className="border-l-2 border-divider pl-3 text-sm">
              <div className="font-medium">{describeConstraint(constraint, labels)}</div>
              {source ? (
                <div className="text-muted">
                  From note: <QuotedText text={source.note} quotes={source.quote ? [{ quote: source.quote, label: 'quote' }] : []} />
                </div>
              ) : (
                <div className="text-muted">Entered directly (no note).</div>
              )}
            </li>
          )
        })}
      </ol>
      <AddConstraint plan={plan} labels={labels} />
    </div>
  )
}

function AddConstraint({ plan, labels }: { plan: StoredDecision; labels: Labels | undefined }) {
  const identity = useIdentity()
  const navigate = useNavigate()
  const [note, setNote] = useState('')
  const [proposal, setProposal] = useState<ConstraintProposal | null>(null)
  const translate = useTranslate()
  const replan = usePlan()
  if (!identity || identity.role === 'viewer') return null

  const confirm = () => {
    if (!proposal?.constraint) return
    replan.mutate(
      {
        scenario: plan.scenario,
        constraints: [...plan.constraints, proposal.constraint],
        constraintSources: [...plan.constraint_sources, { note: proposal.note, quote: proposal.quote }],
      },
      { onSuccess: (next) => void navigate({ to: '/plans/$decisionId', params: { decisionId: next.decision_id } }) },
    )
  }

  return (
    <form
      className="space-y-2 border-t border-divider pt-2"
      onSubmit={(event) => {
        event.preventDefault()
        setProposal(null)
        translate.mutate({ note, scenario: plan.scenario }, { onSuccess: setProposal })
      }}
    >
      <label htmlFor="constraint-note" className="block text-sm font-medium">
        Add a constraint from a note
      </label>
      <textarea
        id="constraint-note"
        value={note}
        onChange={(event) => setNote(event.target.value)}
        rows={2}
        placeholder="e.g. Gomti Nagar side ke liye ek boat rok ke rakho"
        className="w-full rounded border border-control-border bg-bg px-2 py-1 text-sm"
      />
      <Button type="submit" disabled={!note.trim() || translate.isPending}>
        {translate.isPending ? 'Reading note…' : 'Propose constraint'}
      </Button>
      {translate.isError && <Notice tone="high">{translate.error.message}</Notice>}
      {proposal?.status === 'rejected' && (
        <Notice tone="high">
          Not usable: {proposal.explanation}
          {proposal.reasons.length > 0 && <ul className="list-disc pl-5">{proposal.reasons.map((r) => <li key={r}>{r}</li>)}</ul>}
        </Notice>
      )}
      {proposal?.status === 'needs_confirmation' && proposal.constraint && (
        <div className="space-y-2 border border-control-border p-2 text-sm">
          <div className="font-medium">{describeConstraint(proposal.constraint, labels)}</div>
          <div className="text-muted">{proposal.explanation}</div>
          {proposal.quote && <Mono>“{proposal.quote}”</Mono>}
          <div className="flex gap-2">
            <Button onClick={confirm} disabled={replan.isPending}>
              {replan.isPending ? 'Re-planning…' : 'Confirm and re-plan'}
            </Button>
            <Button onClick={() => setProposal(null)}>Discard</Button>
          </div>
          {replan.isError && <Notice tone="high">{replan.error.message}</Notice>}
        </div>
      )}
    </form>
  )
}
