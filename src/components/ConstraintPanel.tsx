import { useState } from 'react'
import { translateNote } from '../api'
import type { ConstraintProposal, PlanningConstraint, Scenario } from '../types'
import { Panel } from './Panel'
import { ActionButton, SecondaryButton } from './buttons'

interface ConstraintPanelProps {
  scenario: Scenario
  confirmed: PlanningConstraint[]
  onConfirm: (constraint: PlanningConstraint, explanation: string) => void
  onRemove: (index: number) => void
  explanations: string[]
}

/** Operator notes become constraints only through an explicit Confirm: the model proposes,
 * the operator decides, and only confirmed constraints go to the solver. */
export function ConstraintPanel({ scenario, confirmed, onConfirm, onRemove, explanations }: ConstraintPanelProps) {
  const [note, setNote] = useState('')
  const [proposal, setProposal] = useState<ConstraintProposal | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const propose = async () => {
    setBusy(true)
    setError(null)
    setProposal(null)
    try {
      setProposal(await translateNote(note, scenario))
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Could not translate the note.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Panel className="mb-5">
      <h3 className="panel-heading">Operator constraints</h3>
      <p className="mt-1 text-xs text-ink-500">
        Write a note (English, Hindi or Hinglish). It becomes a proposed constraint; nothing changes the plan until you confirm it.
      </p>
      <div className="mt-3 flex flex-col gap-2 sm:flex-row">
        <label className="sr-only" htmlFor="constraint-note">Operator note</label>
        <input
          id="constraint-note"
          value={note}
          onChange={(event) => setNote(event.target.value)}
          placeholder="e.g. Gomti Nagar side ke liye ek boat rok ke rakho"
          className="w-full border border-ink-300 bg-paper-sunken px-3 py-2 text-sm text-ink-800 placeholder:text-ink-400"
        />
        <ActionButton onClick={() => void propose()} loading={busy} disabled={note.trim().length < 3}>
          Propose
        </ActionButton>
      </div>
      {error && <p role="alert" className="mt-2 text-xs text-status-blocked">{error}</p>}
      {proposal && (
        <div className="mt-3 border border-ink-300 bg-paper-raised p-3 text-sm">
          <p className="text-ink-800">{proposal.explanation}</p>
          {proposal.quote && <p className="mt-1 text-xs text-ink-500">From: “{proposal.quote}”</p>}
          <div className="mt-2 flex gap-2">
            {proposal.constraint ? (
              <ActionButton
                onClick={() => {
                  if (proposal.constraint) onConfirm(proposal.constraint, proposal.explanation)
                  setProposal(null)
                  setNote('')
                }}
              >
                Confirm constraint
              </ActionButton>
            ) : null}
            <SecondaryButton onClick={() => setProposal(null)}>Discard</SecondaryButton>
          </div>
        </div>
      )}
      {confirmed.length > 0 && (
        <ul className="mt-3 space-y-1 text-xs">
          {confirmed.map((constraint, index) => (
            <li key={`${constraint.kind}-${index}`} className="flex items-center justify-between gap-2 border-l-2 border-accent-700 pl-2">
              <span className="text-ink-800">{explanations[index] ?? constraint.kind}</span>
              <SecondaryButton onClick={() => onRemove(index)}>Remove</SecondaryButton>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}
